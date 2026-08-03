import re
import sys

# This re matches the $( msi syntax until the first ) or (
macro_start = re.compile(r'\$\(([^\(\)]*)')

# This re matches a ( until the next ) or (
bracket_open = re.compile(r'(\([^\(\)]*)')

# This re matches a ) until the next ) or (
bracket_close = re.compile(r'(\)[^\(\)]*)')

# This re matches an line like #% autosave 1 or # % gda_tag, template, ...
epics_parser_re = re.compile(r'^#[ \t]*%')

# This re matches a macro description line like #% macro, P, Pv Prefix.
# It will also match multiline descriptions like:
#% macro, P, Pv Prefix with
# a very long macro
# A description is terminated by a 'blank' line which may optionally contain
# a hash and multiple spaces or tabs.
macro_desc_re = re.compile(
    r'^#[ \t]*%[ \t]*macro[ \t]*,[ \t]*' # This is the #% macro, prefix
    r'([^, \t]+)[ \t]*,[ \t]*' # Captures the macro name and discards comma
    r'([^\n]+' # This start the description capture and the first line
    r'(?:\n#[ \t]*[^\n \t%#][^\n]*)*)', # subsequent non-'blank' line
    re.MULTILINE)


class Substitution():

    TemplateBaseDir = '/dls_sw/prod/R3.14.12.7/support'
    TemplateDir = ""
    TemplateFile = None
    Macros = None
    Defaults = {}
    Descriptions = {}
    _all_subclasses = []

    ## Set this to False to supress warnings on undescribed macros
    WarnMacros = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.instances = []
        if 'Macros' not in cls.__dict__:
            # if not explicitly set, reset such that each subclass gets its own Macros
            cls.Macros = None
        cls.Defaults = {}   # prevent inheriting parent's parsed defaults


    def __init__(self, **kwargs):
        if self.Macros is None:
            self.parse_template()
        args = {**self.Defaults, **kwargs}
        # validate
        missing = [m for m in self.Macros if m not in args]
        extra = [k for k in args if k not in self.Macros]
        if missing:
            raise ValueError("Missing macros: %s" % missing)
        if extra:
            raise ValueError("Unexpected macros: %s" % extra)
        # store
        self.args = args
        #instance tracking
        if not self.instances:
            Substitution._all_subclasses.append(self.__class__)
        self.instances.append(self)


    # Outputs the substitution pattern line associated with this Substitution.
    # This is output in a format suitable for inclusion within a substitutions
    # file.
    @classmethod
    def _print_pattern(cls, file=sys.stdout):
        if cls.Macros:
            print('pattern {', ', '.join(cls.Macros), '}', file=file)

    # Outputs a single substitution line, in order of arguments.  This should
    # be preceded by a call to _print_pattern().
    def _print_substitution(self, file=sys.stdout):
        if self.Macros:
            print('    {', ', '.join(
                [quote_argument(self.args[macro]) for macro in self.Macros]),
                '}', file=file)

    # Outputs the substitution pattern and all substitutions for this class.
    @classmethod
    def print_substitutions(cls, file=sys.stdout):
        if cls.Descriptions:
            print("# Macros:", file=file)
            width = max(len(macro) for macro in cls.Descriptions)
            for macro, description in cls.Descriptions.items():
                print(f'#  {macro:<{width}}  {description}', file=file)
        print(f'file {cls.TemplateBaseDir}/{cls.TemplateDir}/db/{cls.TemplateFile}', file=file)
        print('{', file=file)
        cls._print_pattern(file=file)
        for instance in cls.instances:
            instance._print_substitution(file=file)
        print('}\n', file=file)

    @classmethod
    def write_all_substitutions(cls, filename):
        with open(filename, 'w') as f:
            for subclass in cls._all_subclasses:
                subclass.print_substitutions(file=f)

    @classmethod
    def parse_template(cls):
        if cls.TemplateFile is None:
            raise ValueError("TemplateFile not defined for class %s" % cls.__name__)
        text = open(cls.TemplateBaseDir + '/' + cls.TemplateDir + '/db/' + cls.TemplateFile).read()
        required_names = []
        default_names = []
        default_values = []
        optional_names = []
        Obs = {}
        for line in text.splitlines():
            # find all macro names
            for mtext in find_macros(line):
                if '=' in mtext:
                    # this a macro with a default value
                    mtext, default = mtext.split('=', 1)
                    # check it's not a required value
                    if mtext in required_names + optional_names:
                        print('***Warning: Redefining non-default macro "%s" to have '\
                        'default "%s" in "%s"' % (mtext, default, cls.TemplateFile), file=sys.stderr)
                        required_names = [x for x in required_names if x != mtext]
                        optional_names = [x for x in optional_names if x != mtext]
                    if mtext in default_names:
                        # if it's a default value already, check it matches
                        old_default = default_values[default_names.index(mtext)]
                        if default != old_default:
                            print('***Warning: Cannot set macro "%s" to "%s", already '\
                            'defined with value "%s" in "%s"' % (mtext, default, \
                                old_default, cls.TemplateFile), file=sys.stderr)
                    else:
                        # add it as a default value
                        default_names.append(mtext)
                        default_values.append(default)
                else:
                    # this is a required or optional macro
                    # strip off any msi ,undefined and ,recursive stuff
                    if mtext.endswith(',undefined'):
                        mtext = mtext.replace(',undefined', '')
                    elif mtext.endswith(',recursive'):
                        mtext = mtext.replace(',recursive', '')
                    if mtext in default_names:
                        print('***Warning: Cannot define non-default macro "%s", already '\
                        'defined as default macro in "%s"' % (mtext, cls.TemplateFile), file=sys.stderr)
                    elif line.startswith('#'):
                        # comments are optional if they are epics_parser lines
                        if epics_parser_re.match(line):
                            if mtext not in optional_names:
                                optional_names.append(mtext)
                    else:
                        if mtext not in required_names:
                            required_names.append(mtext)

        # find all the descriptions for ArgInfo objects
        def add_ob(name: str, ob: str):
            Obs[name] = ob
            for l in (required_names, default_names, optional_names):
                if name in l:
                    # shift it to the end
                    if l is default_names:
                        default_values.append(
                            default_values.pop(default_names.index(name)))
                    l.append(l.pop(l.index(name)))


        for name, desc in macro_desc_re.findall(text):
            desc = desc.strip() # needed in case of CRLF separators in template (e.g. windows based modules)
            search = re.search(r'\n#[ \t]*', desc)
            if search:
                desc = re.sub(search.group(), '\n', desc)
            if name == '__doc__':
                doc = desc
            elif name in required_names + default_names + optional_names:
                add_ob(name, desc)
            elif cls.WarnMacros:
                print('***Warning: Describing non-existent macro "%s" in "%s"' % \
                        (name, cls.TemplateFile), file=sys.stderr)
        for name in required_names + default_names + optional_names:
            if name not in Obs:
                if cls.WarnMacros:
                    print('***Warning: Undescribed macro "%s" in "%s"' % \
                        (name, cls.TemplateFile), file=sys.stderr)
                add_ob(name, 'Template argument')
        # make sure optional_names aren't also required names
        optional_names = [x for x in optional_names if x not in required_names]

        # store Macros
        cls.Macros = required_names + default_names + optional_names
        # create Defaults
        cls.Defaults = dict(list(zip(
            default_names + optional_names,
            default_values + ['' for x in optional_names])))

        cls.Descriptions = Obs


# This iterator will find any $(...) macro in line. The number of ( brackets
# ) and brackets in the expression will match
def find_macros(line):
    bracket = 0
    i = 0
    macro = ''

    while i < len(line):
        if bracket > 0:
            # we're in a macro
            match = bracket_open.match(line, i)
            if match:
                # we've opened another bracket
                bracket += 1
            else:
                # we've closed a bracket
                match = bracket_close.match(line, i)
                bracket -= 1
            if bracket == 0:
                # we've closed the macro bracket
                if macro_start.search(macro):
                    for m in find_macros(macro):
                        yield m
                yield macro
                macro = ''
                i += 1
            else:
                # we've closed a non-macro bracket
                macro += match.groups()[0]
                i = match.end()
        else:
            # we're not in a macro, find the start of the next one
            match = macro_start.search(line, i)
            if match:
                i = match.end()
                macro += match.groups()[0]
                bracket = 1
            else:
                i = len(line)


# Converts a string into a form suitable for passing to the database expansion
# and substitution framework.
def quote_argument(argument):
    # According to the msi documentation at
    #    http://www.aps.anl.gov/asd/controls/epics/EpicsDocumentation/
    #        ExtensionsManuals/msi/msi.html
    # it is enough to quote backquotes (and presumably backslashes).
    def quote_char(char):
        if char in '"\\':
            return '\\' + char
        else:
            return char
    return '"' + ''.join(map(quote_char, str(argument))) + '"'
