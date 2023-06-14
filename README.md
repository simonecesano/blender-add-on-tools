# add-on tools

These are tools that make creating add-ons easier - hopefully

## make_add_on.py

This is a simple-ish command line tool that takes a sort of config file and scaffolds an add-on package.

### usage

```
usage: make_add_on.py [-h] [--name NAME] [--dump] [--pack] [--link LINK] [addon_config_file]

positional arguments:
  addon_config_file

optional arguments:
  -h, --help            show this help message and exit
  --name NAME, -n NAME  The name of the addon
  --dump, -d            Dump module definition as JSON and exit
  --pack, -p            Pack module into zip file
  --link LINK, -l LINK  Link module folder to target folder (ideally the Blender add-ons folder
```

- __pack__ basically prepares your module for distribution
- __link__ creates a link between your development folder and your destination folder - typically wherever blender looks for add-ons on your system

### Caveats

- None of this is tested on Windows
- all of this works only from the folder your add-on will be created in
- all of this will mercilessly clobber your files
- creating shortcuts is unimplemented 
- there is no way of adding comments into a config file

Some of these caveats are meant to disappear some day, some not.

### The config file

The config file consists of 3 sections:

- properties: the property definitions
- panel: this determines what the add-on panel will look like
- shortcuts: this determines the shortcuts

As a rule:

- sections begin with a hash ("#" - think markdown)
- config lines fields are separated by pipes ("|")
- everything that comes after a hash ("#") that isn't at the beginning of a line will become explanatory stuff (like property text text)
- empty lines are ignored
- things (like property type)are often case-sensitive

#### Properties

They have 3 fields:

- name
- type (Float, String etc.) - which is optional
- options (multiple ones separated by commas) - optional too

Everything after the "#" becomes the description.

So:

    Minimum Distance|float|min=0.0,max=1.0

is a float called "Minimum distance" with min and max options and

    People|enum|items=[("eeny", "Eeny", ""),("meeny", "Meeny", ""),("miney", "Miney", ""),("mo", "Mo", "")]

is an enum with 3 options.

If you just provide a name, the line will result in a String property

#### Panel

Things happen pretty much automagically here:

- lines beginning with two hashes and a space become headers
- lines beginning with two (or more) dashes become separators
- lines containing a variable name become input fields connected to said variable
- everything else becomes an operator

Operators become operator classes in files according to these rules:

- separators create new files
- these files contain all operators listed up to the next separator
- files get their name from either
  - the following header
  - the text following the two dashes
  - the first operator listed after the separator

#### Shortcuts

These are unimplemented

### What gets created

- a Properties file
- an ```__init__``` file
- a ```Modal.py``` which doesn't do anything for now
- a ```Panel.py``` file containing the panel definition
- a number of files containing the operator classes
