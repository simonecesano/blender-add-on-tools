import sys
import re
import os
import argparse
import pprint
import datetime
import zipfile
import json

from itertools import groupby, chain
from jinja2 import Template, Environment

parser = argparse.ArgumentParser()

parser.add_argument('name', help='The name of the addon')
parser.add_argument('addon_config_file', nargs='?', help='The path to the config file')

parser.add_argument("--update", "-u", action='store_true', help='Update files even if they exist')
parser.add_argument("--dump", "-d", action='store_true', help='Dump module definition and exit')
parser.add_argument("--pack", "-p", action='store_true', help='Pack module into zip file')
parser.add_argument("--link", "-l", type=str, help='Link module folder to target folder (ideally the Blender add-ons folder)')

parser.add_argument("--verbose", "-v", action='store_true', help='Print more messages')

args = parser.parse_args()

prop_types = [
    'BoolProperty',
    'BoolVectorProperty',
    'CollectionProperty',
    'EnumProperty',
    'FloatProperty',
    'FloatVectorProperty',
    'IntProperty',
    'IntVectorProperty',
    'PointerProperty',
    'RemoveProperty',
    'StringProperty'
]

def indexes(items, flt, and_last=False):
    idx = []
    if isinstance(flt, type(re.compile(''))):
        idx = [ i for i, o in enumerate(items) if re.findall(flt, o) ]
    elif isinstance(flt, type(lambda: None)):
        idx = [ i for i, o in enumerate(items) if flt(o) ]
    else:
        idx = [ i for i, o in enumerate(items) if flt == o ]

    if and_last: idx.append(len(items))
    return idx

def first_idx(items, filter):
    idxs = indexes(items, filter)
    return idxs[0] if idxs else None

def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def name_to_camel(name):
    return re.sub(r"\s+", "_", name).lower()

def compress_files(directory, version=None, extensions=['.py', '.blend', '.svg']):
    if not version:
        for root, dirs, files in os.walk(directory):
            version = datetime.datetime.fromtimestamp(max(os.path.getmtime(os.path.join(root, f)) for f in files)).strftime('%Y%m%d%H%M%S')
    zip_filename = "{}-{}.zip".format(directory, version)

    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, file_path)
    return zip_filename

def line_to_property(line, prop_types):
    defaults = ["", "string", ""]
    line, description = re.split(r'\s*\#\s*', line) if re.search(r'\s*\#\s*', line) else (line, "")
    r = re.split(r'\s*\|\s*', line)
    result = [r[i] if i < len(r) else defaults[i] for i in range(3)]
    return {
        "name": result[0],
        "id":   name_to_camel(result[0]),
        "description": description if description else "Enter " + result[0].lower(),
        "type": next(iter([p for p in prop_types if p.lower().startswith(result[1].lower())])),
        "opts": result[2],
    }

def line_to_panel_item(op, addon_vars):
    op_is_a_var = op in [ var["id"] for var in addon_vars ] or op.lower() in [ var["name"].lower() for var in addon_vars ]

    if   op.startswith("## "):      return { "name": op.replace("## ", ""), "type": "label" }
    elif re.findall(r'^-{2,}', op): return { "name": "", "type": "separator" }
    elif op_is_a_var:               return { "name": name_to_camel(op), "type": "prop" }
    else:                           return { "name": name_to_camel(op), "type": "operator", "text": op }


    
def line_to_shortcut(line):
    items = [ i.lower() for i in re.split(r'\s*\-\s*', line) ][::-1]
    shortcut = { "line": line }
    modifiers = [ "shift", "alt", "ctrl", "oskey" ]
    numbers = [ "ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE" ]
    for i in items:
        if i in modifiers:
            shortcut[i] = True
        elif re.match(r'^[a-z]$', i):
            shortcut["type"] = '"{}"'.format(i.upper())
        elif re.match(r'^[0-9]$', i):
            shortcut["type"] = '"{}"'.format(numbers[int(i)])
        elif re.match(r'^[a-z_]+$', i):
            shortcut["type"] = '"{}"'.format(i.upper())
        else:
            shortcut["ascii"] = '"{}"'.format(i)

    shortcut["template"] = " and ".join([ 'event.{} == {}'.format(t, v) for t, v in shortcut.items() if not t == "line"])
    shortcut["template"] = shortcut["template"] + " # " + shortcut["line"]
    return shortcut
    

def file_to_addon_conf(file_path):
    with open(file_path, "r") as file: lines = [ l.strip() for l in file.readlines() if l.strip() ]

    comment_re = re.compile(r'\s*%%.+')
    block_re = re.compile(r'^# ')
    module_re = re.compile(r'^## |\-{2,} *')

    lines = [ comment_re.sub("", l) for l in lines ]
    lines = [ l for l in lines if l ]

    idx = indexes(lines, block_re, and_last=True)
    addon = {}

    for i in range(0, len(idx)-1): addon[block_re.sub("", lines[idx[i]])] = lines[idx[i]+1:idx[i+1]]
    idx = indexes(addon["panel"], module_re, and_last=True)

    addon["properties"] = [ line_to_property(p, prop_types) for p in addon["properties"] ] 
    addon["modules"] = []
    addon["imports"] = []
    addon["operators"] = []

    for i in range(0, len(idx)-1):
        addon["modules"].append([module_re.sub("", addon["panel"][idx[i]]), addon["panel"][idx[i]+1:idx[i+1]]])

    for mod in addon["modules"]:
        mod[1] = [ { "name": name_to_camel(op), "label": op } for op in mod[1] ]
        mod[1] = [ op for op in mod[1] if op["name"] not in [ prop["id"] for prop in addon["properties"] ] ]
        mod[0] = name_to_camel(mod[0]) if mod[0] else mod[1][0]["name"]
        for op in mod[1]: addon["operators"].append(op["name"])
        addon["imports"].append(mod[0])

    addon["shortcuts"] = [ line_to_shortcut(l) for l in addon["shortcuts"] ]
    
        
    addon["panel"]      = [ line_to_panel_item(p, addon["properties"]) for p in addon["panel"] ] 
    return addon

def read_templates():
    source_code = []
    with open(__file__, 'r') as file: source_code = file.readlines()
    start_index = None
    templates = {}
    for index, line in enumerate(source_code):
        if line.strip() == '# Start of template section':
            start_index = index + 1  # Start of the next line after the marker
            exec("".join(source_code[start_index:]), {}, templates)
    return { key: value.strip('\n') for key, value in templates.items() }

def compile_template(template_source, output_file, update=False, **vars):
    source = Template(template_source).render(**vars)
    if update or not os.path.exists(output_file):
        with open(output_file, "w") as file: file.write(source)
    else:
        with open(output_file, 'r') as file:
            prev_source = file.read()
            if prev_source != source: print("File {} exists - use update option to overwrite".format(output_file), file=sys.stderr)
    return source

def create_add_on(templates, addon, args):
    if args.verbose: print("Creating module {}".format(args.name), file=sys.stderr)

    if not os.path.isdir(args.name):
        os.mkdir(args.name)
        if args.verbose: print("Creating folder {}".format(args.name), file=sys.stderr)

    for mod in addon["modules"]:
        name, ops = mod
        file_path = os.path.join(args.name, name + ".py")
        if args.verbose: print("Creating file {}".format(file_path), file=sys.stderr)
        compile_template(templates["operator"], file_path, update=args.update, operators=ops, name=args.name)

    for mod_file in ["Properties", "Modal", "Panel", "__init__"]:
        file_path = os.path.join(args.name, mod_file + ".py")
        if args.verbose: print("Creating file {}".format(file_path), file=sys.stderr)
        compile_template(templates[mod_file.lower()], file_path, update=args.update, addon=addon, name=args.name)

 
if args.link:
    source_folder = os.path.abspath(args.name)
    target_folder = os.path.abspath(os.path.join(args.link, args.name))
    os.symlink(source_folder, target_folder)    

    if args.verbose: print("Created link to {} in {}".format(source_folder, target_folder), file=sys.stderr)
    exit()
    
if args.pack:
    zipfile = compress_files(args.name)
    if args.verbose: print("Created add-on {}".format(zipfile), file=sys.stderr)
    
    exit()

addon = file_to_addon_conf(args.addon_config_file)
    
if args.dump:
    import json
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(addon)
    print(json.dumps(addon, indent=4))
    exit()

templates = read_templates()
create_add_on(templates, addon, args)


# ================================================
# Start of template section
# ================================================

properties='''
import bpy

class {{ name }}Properties(bpy.types.PropertyGroup):
{%- for prop in addon["properties"] %}
    {{ prop.id }}: bpy.props.{{ prop.type }}(
        name="{{ prop.name }}",
        description="{{ prop.description }}",
        {% if prop.opts -%}{{ prop.opts }},{%- endif %}
    )
{%- endfor %}
'''

panel='''
import bpy

{%- for mod in addon["imports"] %}
from . {{ mod }} import * 
{%- endfor %}
from . Properties import {{ name }}Properties

class {{ name }}Panel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_{{ name.lower() }}_panel"
    bl_label = "{{ name }} Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '{{ name }}'

    def draw(self, context):
        layout = self.layout
        {%- for op in addon["panel"] %}
        {% if op.type == "separator" -%}
        layout.separator()
        {% elif op.type == "label" -%}
        layout.label(text="{{ op.name }}")
        {% elif op.type == "operator" -%}
        layout.operator("object.{{ name.lower() }}_{{ op.name }}", text="{{ op.text }}")
        {%- else -%}
        layout.prop(context.scene.{{ name.lower() }}, "{{ op.name }}")
        {%- endif %}
        {%- endfor %}
'''

operator='''
import bpy
import os
import sys

from bpy.types import (Operator)
{% for op in operators %}
class {{ name.upper() }}_OP_{{ op.name }}(Operator):
    bl_label  = "{{ op.label }}"
    bl_idname = "object.{{ name.lower() }}_{{ op.name }}"
    
    def execute(self, context):
        print("{{ name.upper() }}_OP_{{ op.name }} unimplemented")
        return {'FINISHED'}
{% endfor %}
'''

modal = '''
import bpy

from bpy.app.handlers import persistent

@persistent
def {{ name.lower() }}_modal_startup(dummy):
    area_3d = next(iter([area for area in bpy.context.screen.areas if area.type == "VIEW_3D"]))
    if area_3d:
        region = next(iter([region for region in area_3d.regions if region.type == 'WINDOW']))
        print("Registering {{ name }}ModalOperator in load_post handler")
        with bpy.context.temp_override(area=area_3d, region=region):
            bpy.ops.object.{{ name.lower() }}_modal_operator('INVOKE_DEFAULT')

bpy.app.handlers.load_post.append({{ name.lower() }}_modal_startup)

def {{ name.lower() }}_modal_timer():
    area_3d = next(iter([area for area in bpy.context.screen.areas if area.type == "VIEW_3D"]))
    if area_3d:
        region = next(iter([region for region in area_3d.regions if region.type == 'WINDOW']))
        print("Registering {{ name }}ModalOperator in timer")
        with bpy.context.temp_override(area=area_3d, region=region):
            bpy.ops.object.{{ name.lower() }}_modal_operator('INVOKE_DEFAULT')
        return None
    return 0.1

class {{ name }}ModalOperator(bpy.types.Operator):
    """The {{ name }} modal operator"""

    bl_idname = "object.{{ name.lower() }}_modal_operator"
    bl_label = "{{ name }} Modal Operator"
    
    letters = [chr(i) for i in range(ord('A'), ord('Z')+1)]
    numbers = [ "ZERO", "ONE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE" ]
    arrows =  [ 'LEFT_ARROW', 'DOWN_ARROW', 'RIGHT_ARROW', 'UP_ARROW' ]
    mouse =   [ 'LEFTMOUSE', 'MIDDLEMOUSE', 'RIGHTMOUSE' ]
    
    def modal(self, context, event):
        area = context.area
        is_inside = area.x < event.mouse_x < area.x + area.width and area.y < event.mouse_y < area.y + area.height
        
        if event.type == 'ESC':
            return {'PASS_THROUGH'}
        elif event.type in self.letters and event.value == "PRESS":
            print(__name__, event.type, event.ctrl, event.shift, event.alt, event.oskey, area.type)
        elif event.type in self.numbers and event.value == "PRESS":        
            print(__name__, event.type, event.ctrl, event.shift, event.alt, event.oskey, area.type)
        elif event.type in self.arrows  and event.value == "PRESS":
            print(__name__, event.type, event.ctrl, event.shift, event.alt, event.oskey, area.type)
        elif event.type in self.mouse   and event.value == "PRESS":
            print(__name__, event.type, event.ctrl, event.shift, event.alt, event.oskey, is_inside)
        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if context.area.type in [ 'VIEW_3D' ]:
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "This might not be the right window to call this in")
            return {'CANCELLED'}
    
    def register():
        bpy.app.timers.register({{ name.lower() }}_modal_timer)
        
    def unregister():
        if bpy.app.timers.is_registered({{ name.lower() }}_modal_timer):
            bpy.app.timers.unregister({{ name.lower() }}_modal_timer)

if __name__ == "__main__":
    register()
'''

__init__ = '''
import bpy
import os
import sys

from importlib import reload
{% set operators = addon["operators"] %}
bl_info = {
    "name": "{{ name }}",
    "author": "simone cesano",
    "version": (0, 0, 1),
    "blender": (2, 80, 0),
    "location": "View3D > Tools > {{ name }}",
    "description": "A {{ name }} tool",
    "warning": "",
    "category": "Material",
}

from . Panel import *
from . Properties import *
from . Modal import *
{%- for imp in imports %}
from . {{ imp }} import *
{%- endfor %}

for m in [ m for m in sys.modules if str(m).startswith(__name__) ]:
    print("Found module " + m)

class_list = (
    {{ name }}Panel,
    {{ name }}Properties,
    {{ name }}ModalOperator,
    {%- for op in operators %}
    {{ name.upper() }}_OP_{{ op }},
    {%- endfor %}
)

def register():
    for cls in class_list:
        print("Registering {}".format(cls.__name__))
        bpy.utils.register_class(cls)
    bpy.types.Scene.{{ name.lower() }} = bpy.props.PointerProperty(type={{ name }}Properties)

def unregister():
    for cls in class_list:
        print("Unregistering {}".format(cls.__name__))
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.{{ name.lower() }}
'''
