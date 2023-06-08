import sys
import re
import argparse
from jinja2 import Template

parser = argparse.ArgumentParser()

parser.add_argument("--vars", "-v", type=str)
parser.add_argument("--ops", "-o",  type=str)
parser.add_argument("--name", "-n", type=str)

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
    
def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()

def name_to_camel(name):
    return re.sub(r"\s+", "_", name).lower()

def read_templates():
    source_code = []
    with open(__file__, 'r') as file:
        source_code = file.readlines()
    start_index = None
    templates = {}
    for index, line in enumerate(source_code):
        if line.strip() == '# Start of template section':
            start_index = index + 1  # Start of the next line after the marker
            exec("".join(source_code[start_index:]), {}, templates)
    return { key: value.strip('\n') for key, value in templates.items() }

def line_to_property(line, prop_types):
    defaults = ["", "string", ""]
    r = re.split(r'\s*\|\s*', line)
    result = [r[i] if i < len(r) else defaults[i] for i in range(3)]

    prop = {}
    prop["name"]        = result[0]
    prop["id"]          = name_to_camel(result[0])
    prop["description"] = "Enter " + result[0].lower()
    prop["type"]        = next(iter([p for p in prop_types if p.lower().startswith(result[1].lower())]))
    prop["opts"]        = result[2]

    return prop

def line_to_operator(line):
    return line

templates = read_templates()

# ------------------------------------------------
# Properties section
# ------------------------------------------------
with open(args.vars, "r") as file: lines = [ l.strip() for l in file.readlines() ]
properties= [ line_to_property(line, prop_types) for line in lines ]

# ------------------------------------------------
# Panel section
# ------------------------------------------------
with open(args.ops, "r") as file: lines = [ l.strip() for l in file.readlines() ]
operators = [ line_to_operator(line) for line in lines ]


print(Template(templates["properties"]).render(properties=properties, name=args.name))

print("\n# " + ("-" * 96) + "\n")

print(Template(templates["panel"]).render(operators=operators, properties=[ p["id"] for p in properties ], name=args.name))

# ================================================
# Start of template section
# ================================================

properties='''
import bpy

class {{ name }}Properties(bpy.types.PropertyGroup):
{%- for prop in properties %}
    {{ prop.id }}: bpy.props.{{ prop.type }}(
        name="{{ prop.name }}",
        description="{{ prop.description }}",
        {% if prop.opts %}{{ prop.opts }}, {% endif %}
    )
{%- endfor %}
'''

panel='''
import bpy

class {{ name }}Panel(bpy.types.Panel):
    bl_idname = "OBJECT_PT_{{ name.lower() }}_panel"
    bl_label = "{{ name }} Panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = '{{ name }}'

    def draw(self, context):
        layout = self.layout
        {%- for op in operators %}
        {% if op not in properties -%} 
        layout.operator("object.{{ name.lower() }}.{{ op }}", text="{{ op }}")
        {%- else -%}
        layout.prop(context.scene.{{ name.lower() }}, "{{ op }}")
        {%- endif %}
        {%- endfor %}

classes = (
    {{ name }}Properties,
    {{ name }}Panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.{{ name.lower() }} = bpy.props.PointerProperty(type={{ name }}Properties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.{{ name.lower() }}

if __name__ == "__main__":
    register()
'''
