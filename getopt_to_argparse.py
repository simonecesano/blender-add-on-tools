import argparse
import re
import sys

def dict_to_string(dictionary):
    items = []
    for key, value in dictionary.items():
        if isinstance(value, type):
            item = f"{key}={value.__name__}"
        else:
            item = f"{key}={value}"
        items.append(item)
    return ', '.join(items)


def make_argdef(opt_strings, desc="", opts={}):
    # 1: options; 2: =:; 3: type; 4: %@

    src = re.compile('(.+?)([\=\:]{1,})(.)([\%\@])*')
    defaults = { "i": 0, "f": 0.0, "s": '""' }
    types    = { "i": int, "f": float, "s": str }
    
    print("import argparse\nfrom functools import reduce\nparser = argparse.ArgumentParser()\n")

    for opt_string in opt_strings:
        opts = {}
        if re.search(r"\t|\s+", opt_string):
            opt_string, opts["help"] = re.split(r"\t|\s", opt_string, maxsplit=1)
            opts["help"] = ''.join(["'", opts["help"], "'"])
            
        match = re.search(src, opt_string)
        if match:
            opts["type"] = types[match[3]]
            if (match[2] == ':'):
                opts['nargs']  = '"?"' if (not 'nargs' in opts) else opts['nargs']
                opts['const']  = defaults[match[3]]
                opts['default'] = None if (not 'default' in opts) else opts['default']
            if (match[4] == '@'):
                opts['nargs'] = '"+"';
                opt_string.replace("@", "")
            elif (match[4] == '%'):
                opts['nargs'] = '"+"';
                opts["action"] = '"append"';
                opts["type"] = "lambda x: dict([x.split('=')])";
                opt_string.replace("%", ""); 
            
            argstr = ", ".join([('"-' + f + '"' if len(f) == 1 else '"--' + f + '"') for f in match[1].split('|')])
            print("parser.add_argument({}, {})".format(argstr, dict_to_string(opts)))
        else:
            argstr = ", ".join([('"-' + f + '"' if len(f) == 1 else '"--' + f + '"') for f in opt_string.split('|')])
            opts["action"] = '"store_true"'
            print("parser.add_argument({}, {})".format(argstr, dict_to_string(opts)))
            
    print("\nargs = parser.parse_args()\n")
    for opt_string in [ o for o in opt_strings if o.endswith("%") ]:
        match = re.search(src, opt_string)
        opt = match[1].split("|")[0]
        print(("args.{} = reduce(lambda d1, d2: {{**d1, **d2}}, " + \
              "[item for sublist in args.{} for item in sublist], {{}}) if args.{} else {{}}") \
              .format(opt, opt, opt))
    print("print(args)")

if len(sys.argv) > 1:
    input_file = sys.argv[1]
    with open(input_file, 'r') as file:
        opts = [ o.strip() for o in file.readlines() ]
else:
    opts = []
    for line in sys.stdin:
        opts.append(line.strip())
        

make_argdef(opts)


    
#     make_argdef('verbose|v')
#     make_argdef('format|f=s')
#     make_argdef('def|d=s')
#     make_argdef('output|o:s')
#     make_argdef('print|p:i')
#     make_argdef('lengths|l=i@')

# zannoni.l@maxmara.it
# rosi.a@maxmara.it
# andrea.biasi@jakala.com
