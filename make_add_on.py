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

parser.add_argument("--name", "-n", type=str)
parser.add_argument("--dump", "-d", action='store_true', help='Dump module definition and exit')
parser.add_argument("--pack", "-p", action='store_true', help='Pack module into zip file')
parser.add_argument("--link", "-l", type=str, help='Link module folder to target folder (ideally the Blender add-ons folder')
parser.add_argument('file', nargs='?')

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
def indexes(items, flt):
    if isinstance(flt, type(re.compile(''))):
        return [ i for i, o in enumerate(items) if re.findall(flt, o) ]
    elif isinstance(flt, type(lambda: None)):
        return [ i for i, o in enumerate(items) if flt(o) ]
    else:
        return [ i for i, o in enumerate(items) if flt == o ]

def first_idx(items, filter):
    idxs = indexes(items, filter)
    return idxs[0] if idxs else None

def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def name_to_camel(name):
    return re.sub(r"\s+", "_", name).lower()

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
    elif re.findall(r'^-{5,}', op): return { "name": "", "type": "separator" }
    elif op_is_a_var:               return { "name": name_to_camel(op), "type": "prop" }
    else:                           return { "name": name_to_camel(op), "type": "operator", "text": op }

def lines_to_modules(lines):
    modules = [[]]
    # ----------------------------
    # one module per separator
    # ----------------------------
    for op in [ op for op in lines if op ]:
        if re.findall(r'^-{5,}', op): modules.append([])
        else:                         modules[-1].append({ "name": name_to_camel(op), "label": op })
        # label is the human-readable thing
    
    for i, module in enumerate(modules):
        if module[0]["label"].startswith("## "):
            modules[i] = { name_to_camel(module[0]["label"].replace("## ","")): module[1:] }
        elif module[0]["label"].startswith("-- "):
            modules[i] = { name_to_camel(module[0]["label"].replace("-- ","")): module[1:] }
        else:
            modules[i] = { module[0]["name"]: module[0:] }
    return modules

def compress_files(directory):
    current_datetime = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    newest_date = 0
    zip_filename = "{}-{}.zip".format(directory, current_datetime)
    extensions = ['.py', '.blend', '.svg'] # this should be configurable
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    file_date = os.path.getmtime(file_path)
                    newest_date = file_date if file_date > newest_date else newest_date
                    zipf.write(file_path, file_path)
    # print(datetime.datetime.fromtimestamp(newest_date).strftime('%Y%m%d%H%M%S'))
    # os.rename(old_filename, new_filename)


# ================================================
# Utils
# ================================================

if args.link:
    source_folder = os.path.abspath(args.name)
    target_folder = os.path.abspath(os.path.join(args.link, args.name))
    os.symlink(source_folder, target_folder)    
    exit()
    
if args.pack:
    compress_files(args.name)
    exit()

# ================================================
# Reading and parsing
# ================================================

def config_to_data(config_file):
    with open(config_file, "r") as file: lines = [ l.strip() for l in file.readlines() if l.strip() ]

    libs = [ g for g in [ list(group) for key, group in groupby(lines, lambda op: op.startswith("# ")) ] ]
 
    vars_idx = [ i for i, o in enumerate(libs) if o[0].lower().startswith("# vars")][0]
    ops_idx  = [ i for i, o in enumerate(libs) if o[0].lower().startswith("# ops")][0]
    shct_idx  = [ i for i, o in enumerate(libs) if o[0].lower().startswith("# shortcuts")][0]

    vars_lines = [ var for var in libs[vars_idx + 1:ops_idx][0] if var ]
    ops_lines  = [ op for op in libs[ops_idx + 1:shct_idx][0] if op ]
    shct_lines = [ op for op in libs[shct_idx + 1:][0] if op ]
    
    addon = {
        "properties": [ line_to_property(var, prop_types) for var in vars_lines if var],
        "modules":    lines_to_modules([ op for op in ops_lines if op ]),
        "operators":  [],
        "panel": [],
        "imports": [],
        "shortcuts": shct_lines
    }
    
    for mod in addon["modules"]:
        addon["imports"].append(list(mod.items())[0][0])
        for op in list(mod.items())[0][1]:
            op_is_a_var = op["name"] in [ var["id"] for var in addon["properties"] ] \
                or op["label"].lower() in [ var["name"].lower() for var in addon["properties"] ]
            if not op_is_a_var:
                addon["operators"].append(op["name"])

    addon["panel"] = list(line_to_panel_item(op, addon["properties"]) for op in ops_lines if op)
    return addon


def create_add_on(templates, addon, mod_name):
    if not os.path.isdir(mod_name): os.mkdir(mod_name)
    for mod in addon["modules"]:
        name, ops = next(iter(mod.items()))
        with open(os.path.join(mod_name, name + ".py"), "w") as file:
            file.write(Template(templates["operator"]).render(operators=ops, name=mod_name))

    for mod_file in ["Properties", "Modal", "Panel", "__init__"]:
        with open(os.path.join(mod_name, mod_file + ".py"), "w") as file:
            file.write(Template(templates[mod_file.lower()]).render(addon=addon, name=mod_name))


# ================================================
# Output
# ================================================

addon = config_to_data(args.file)

if args.dump:
    import json
    # pp = pprint.PrettyPrinter(indent=4)
    # pp.pprint(addon)
    print(json.dumps(addon, indent=4))
    exit()


templates = read_templates()
create_add_on(templates, addon, args.name)
        
# --------------------------------------------------------------
# TODO
# - make all templates dependent on addon def and name only
# - add shortcuts configuration
# - check something weird with operators (more added than necessary)
# --------------------------------------------------------------

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
