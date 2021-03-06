
"""

Reification of nesoni tools.

Metainformation about tools will hopefully allow
- automatic help text
- ability to pickle and pass around specification of job that needs to be done (eg on a cluster)
- Make-like checking of what needs to be re-done

"""


import sys, os, pickle, traceback, textwrap, re, copy, functools, types, datetime

from nesoni import workspace


class Error(Exception): 
    pass


def filesystem_friendly_name(name):
    """ Remove special characters from a name """

    for char in '\'"<>&|/\\_ .':
        name = name.replace(char,'_')
    return name



def colored(color, text):
    return '\x1b[%dm%s\x1b[m' % (color, text)

def strip_color(text):
    return re.sub(r'\x1b\[\d*m','',text)

def write_colored_text(file, text):
    if not file.isatty():
        text = strip_color(text)
    file.write(text)

def wrap(text, width, prefix='', suffix=''):
    result = [ ]
    for line in text.rstrip().split('\n'):
        result.extend(textwrap.wrap(line.rstrip(), width, break_on_hyphens=False, break_long_words=False) or [''])
    return prefix + (suffix+'\n'+prefix).join(result)


def get_flag_value(args, option, conversion_function):
    """ Get a command line option """
    args = args[:]
    value = None
    present = False
    while True:
        try:
            location = args.index(option)
        except ValueError: #Not found
            break
            
        if location == len(args)-1 :
            raise Error('Option %s requires a paramter' % option)
        
        try:
            value = conversion_function(args[location+1])
            present = True
        except Exception:
            raise Error('Option for %s not in expected format' % option)
        
        del args[location:location+2]

    return present, value, args

def expect_no_further_flags(args):
    for arg in args:
        if arg.startswith('-'):
            raise Error('Unexpected flag "%s"' % arg)
        if arg.endswith(':'):
            raise Error('Unexpected section "%s"' % arg)


def execute(args, commands, default_command):
    """ Execute a series of commands specified on the command line.
        
        eg
        [default command param] command: [param ...] command: [param ...]
    """
    command_locations = [ i for i,arg in enumerate(args) if arg in commands ]
    split_points = command_locations + [len(args)]    
    
    default_command(args[:split_points[0]])
    
    for start, end in zip(command_locations, split_points[1:]):
        commands[args[start]](args[start+1:end])

def as_bool(string):
    string = string.lower()
    if string in ('yes','y','true','t'): return True
    if string in ('no','n','false','f'): return False
    value = int(string)
    assert value in (0,1)
    return bool(value)

def describe_bool(boolean):
    if boolean:
        return 'yes'
    else:
        return 'no'


class Parameter(object):
    def __init__(self, name, help=''):
        self.name = name
        self.help = help

    def parse(self, obj, string):
        return string
    
    def describe(self, value):
        return value

    def __call__(self, item):
        # Put the parameter after any parameters from base classes
        # but before any parameters from this class.
        # (parameter decorations are evaluated in reverse order)
        n = 0
        while n < len(item.parameters):
            is_in_base = False
            for base in item.__bases__:
                if item.parameters[n] in base.parameters:
                    is_in_base = True
                    break
            if not is_in_base: break                    
            n += 1
        item.parameters = item.parameters[:n] + (self,) + item.parameters[n:]
        return item
    
    def set(self, obj, value):
        setattr(obj, self.name, value)
    
    def get(self, obj):
        return getattr(obj, self.name)
        
    def describe_shell(self, value, verbose=True):
        if value is None and not verbose: 
            return ''
        return colored(1, self.shell_name()) + ' ' + colored(35 if value is not None else 34, self.describe(value))


class Hidden(Parameter):
    def describe_shell(self, value, verbose=True):
        return ''


class Positional(Parameter): 
    def shell_name(self):
        return '%s' % self.name.replace('_','-').lower()
    
    def parse(self, obj, string):
        expect_no_further_flags([string])
        return string
    
    def describe_shell(self, value, verbose=True):
        if value is None:
            return colored(34, self.shell_name()) if verbose else ''
        else:
            return colored(35, self.describe(value))


class Flag(Parameter):
    def shell_name(self):
        return '--'+self.name.replace('_','-').rstrip('-').lower()


class String_flag(Flag):
    def describe(self, value):
        return value if value is not None else '...'


class Bool_flag(Flag):
    def parse(self, obj, string): 
        return as_bool(string)
        
    def describe(self, value): 
        if value is None: 
            return 'yes/no'
        return describe_bool(value)


class Int_flag(Flag):
    def parse(self, obj, string):
        return int(string)
    
    def describe(self, value):
        if value is None: 
           return 'NNN'
        return '%d' % value


class Float_flag(Flag):
    def parse(self, obj, string):
        return float(string)
    
    def describe(self, value):
        if value is None: 
           return 'N.NN'
        return '%.3f' % value

        

class Section(Parameter):
    def __init__(self, name, help='', allow_flags=False, empty_is_ok=True):
        Parameter.__init__(self,name,help)
        self.allow_flags = allow_flags
        self.empty_is_ok = empty_is_ok

    def parse(self, obj, args):
        if not self.allow_flags:
            expect_no_further_flags(args)
        return self.get(obj) + args

    def shell_name(self):
        return self.name.replace('_','-').rstrip('-').lower()+':'

    def describe(self, value):
        return ' '.join(value)

    def describe_shell(self, value, verbose=True):
        if not verbose and not value: return ''
        return Parameter.describe_shell(self, value, verbose) 


class Grouped_section(Section):
    def parse(self, obj, args):
        if not self.allow_flags:
            expect_no_further_flags(args)
        return self.get(obj) + [ args ]

    def describe(self, value):
        return ' '.join(self.shell_name() + ' ' + ' '.join(item) for item in value)
        
    def describe_shell(self, value, verbose=True):
        if verbose and not value:
            return colored(1, self.shell_name())
        return '\n'.join(
            colored(1, self.shell_name()) + ' ' + colored(35, ' '.join(item))
            for item in value
        )
            

class Float_section(Section):
    def parse(self, obj, args):
        return self.get(obj) + [ float(item) for item in args ]

    def describe(self, value):
        return ' '.join( '%f' % item for item in value )        


class Main_section(Section):
    def shell_name(self):
        return self.name.replace('_','-').rstrip('-').lower()+' ...'

    def describe_shell(self, value, verbose=True):
        if not value:
            if verbose:
                return colored(34, self.shell_name())
            else:
                return ''
        else:
            return colored(35, self.describe(value))


class Configurable_section(Section):
    def __init__(self, name, help='', empty_is_ok=True, allow_none=False):
        super(Configurable_section,self).__init__(name,help=help,allow_flags=True,empty_is_ok=empty_is_ok)
        self.allow_none = allow_none

    def parse(self, obj, args):
        if self.allow_none and len(args) == 1 and args[0].lower() == 'no':
            return None
    
        old = self.get(obj)
        assert old is not None, 'Can\'t modify empty section'        
        new = old()
        new.parse( args )
        return new

    def describe_shell(self, value, verbose=True):
        if value is None:
            return colored(34, self.shell_name()) + ' no'
        return colored(34, self.shell_name()) + value.describe(invocation='')


def help(short, extra=''):
    full = short
    if extra: full += '\n\n' + extra

    def func(item):
        item.help = full
        item.help_short = short
        return item
    return func


def _wrap(func, before, after):
    @functools.wraps(func)
    def inner(self, *args,**kwargs):
        before(self)
        try:
            return func(self,*args,**kwargs)
        finally:
            after(self)
    return inner

class Configurable_metaclass(type):
    def __new__(self, name, bases, dictionary):
        # Inherit parameters from all bases    
        parameters = ()
        for base in bases:            
            if hasattr(base, 'parameters'):
                for parameter in base.parameters:
                    if parameter not in parameters:
                        parameters += (parameter,)
        dictionary['parameters'] = parameters + dictionary.get('parameters',())
        
        if '__doc__' in dictionary:
            dictionary['__doc__original__'] = dictionary['__doc__']
            del dictionary['__doc__']
        
        result = type.__new__(self, name, bases, dictionary)
        
        for name in dictionary:
            if not isinstance(dictionary[name], types.FunctionType): continue
            
            func = dictionary[name]
            entries = [ ]
            exits = [ ]
            before_name = '_before_'+name
            after_name = '_after_'+name
            for item in result.mro():
                if before_name in item.__dict__ or after_name in item.__dict__:
                    func = _wrap(func,item.__dict__.get(before_name,lambda self:None),
                                      item.__dict__.get(after_name,lambda self:None))
            setattr(result, name, func) 
        
        return result 

    @property
    def __doc__(self):
        result = getattr(self,'__doc__original__','')
        result += '\n\n' + wrap(self.help, 70)
        
        result += '\n\nParameters:\n'
        for parameter in self.parameters:
            result += '\n' + parameter.name + ' = ' + repr(parameter.get(self)) + '\n' + wrap(parameter.help, 65, '     # ')
        return result

    def __dir__(self):
        result = [ ]
        for item in self.mro():
            for key, value in item.__dict__.items():
                if key not in result and isinstance(value, types.FunctionType) and not key.startswith('_'):
                    result.append(key)
        return result 


class Configurable(object):
    __metaclass__ = Configurable_metaclass
    
    parameters = ()
        
    help = ''
    help_short = ''
    
    def __init__(self, *args, **kwargs):
        self._modify(*args, **kwargs)

    def __call__(self, *args, **kwargs):
        result = copy.deepcopy(self)
        result._modify(*args, **kwargs)
        return result
    
    def _modify(self, *args, **kwargs):
        unused = set(kwargs)
        for parameter in self.parameters:            
            if isinstance(parameter, Positional) and args:
                value = args[0]        
                args = args[1:]
            elif isinstance(parameter, Main_section) and args:
                value = args
                args = [ ]
            elif parameter.name in kwargs:
                value = kwargs[parameter.name]
                unused.remove(parameter.name)
            else:
                value = parameter.get(self)
            
            # Set all parameters, even unmodified ones,
            # so that values that are just a class default will be pickled    
            parameter.set(self, value)

        assert not unused, 'Unknown named parameter: '+', '.join(unused)
        assert not args, 'Unexpected parameters'         
        
    def parse(self, args):
        kwargs = { }
        for parameter in self.parameters:
            if isinstance(parameter, Flag):
                present, value, args = get_flag_value(args,parameter.shell_name(),lambda item: parameter.parse(self, item))
                if present:
                    parameter.set(self, value)
        
        def default_command(args):
            expect_no_further_flags(args)
            if args:
                raise Error('Unexpected parameters: ' + ' '.join(args))

        commands = { }
        
        for parameter in self.parameters:
            if isinstance(parameter, Section):
                def command(args, self=self,parameter=parameter):
                    value = parameter.parse(self, args)
                    parameter.set(self, value) 
            
                if isinstance(parameter, Main_section):
                    default_command = command
                else:
                    commands[parameter.shell_name()] = command
         
        def outer_default_command(args):
            for parameter in self.parameters:
                if args and isinstance(parameter, Positional):
                    parameter.set(self, parameter.parse(self, args[0]))
                    args = args[1:]
            default_command(args)
        
        execute(args, commands, outer_default_command)

    @classmethod
    def shell_name(self):
        return self.__name__.lower().replace('_','-').strip('-')
    
    def ident(self):
        return self.shell_name()
    
    def __repr__(self):
        return '<'+self.ident()+'>'
    
    def __cmp__(self, other):
        c = cmp(self.__class__, other.__class__)
        if c: return c
        for parameter in self.parameters:
            c = cmp(parameter.get(self), parameter.get(other))
            if c: return c
        return 0
    
    def describe(self, invocation=None, show_help=False):
        if invocation is None:
            invocation = self.shell_name() + ':'
    
        desc = [ colored(1, invocation) ]
        
        flags = [ item for item in self.parameters if isinstance(item, Flag) ]
        non_flags = [ item for item in self.parameters if not isinstance(item, Flag) ]
        
        if show_help:
            suffix = ''
        else:
            suffix = ' \\'
        
        for parameter in flags + non_flags:
            line = parameter.describe_shell(parameter.get(self), show_help)
            if line:
                desc.append(wrap(line,67,'    ',suffix))
                if show_help and parameter.help:
                    desc.append(colored(30,wrap(parameter.help,65,'    # ')))
       
        return (colored(2,suffix)+'\n').join( desc ) + '\n'
    

class Action(Configurable):
    run = NotImplemented

    def cores_required(self):
        return 1
    
    def make(self):
        from nesoni import legion
        legion.make(self)

    def process_make(self):
        from nesoni import legion
        legion.process_make(self)



class Action_with_log(Action):
    log_filename = NotImplemented
    
    _log_level = 0
    
    def _before_run(self):
        if self._log_level == 0:
            filename = self.log_filename()
            if filename is not None and os.path.exists(filename):
                os.unlink(filename)
        
            self._log_start = datetime.datetime.now()
        
            import nesoni
            from nesoni import grace
            self.log = grace.Log()
            self.log.quietly_log(
               '\n'+
               strip_color(self.describe())+'\n'+
               'from '+os.getcwd()+'\n\n'+    
               'nesoni '+nesoni.VERSION+'\n\n'
            )
        self._log_level = self._log_level + 1
    
    def _after_run(self):
        self._log_level = self._log_level - 1
        if self._log_level == 0:
            now = datetime.datetime.now()
            self.log.quietly_log(
                '\n' +
                ' started '+ self._log_start.strftime('%_d %B %Y %_I:%M %p') + '\n'
                'finished '+ now.strftime('%_d %B %Y %_I:%M %p') + '\n'
                'run time '+ str( datetime.timedelta(seconds=int((now-self._log_start).total_seconds())) ) + '\n'
            )

            filename = self.log_filename()
            if filename is not None and os.path.exists(os.path.split(filename)[0] or '.'):
                self.log.attach(open(filename,'ab'))
            self.log.close()
            del self.log
            del self._log_start
            del self._log_level


@Positional('prefix', 'Prefix for output files.')
class Action_with_prefix(Action_with_log):
    prefix = None
    def ident(self):
        return super(Action_with_prefix,self).ident() + '--' + (self.prefix or '') 

    def log_filename(self):
        if self.prefix is None: return None
        return self.prefix + '_log.txt'


@Positional('output_dir', 'Directory for output files (will be created if does not exist).')
class Action_with_output_dir(Action_with_log):
    output_dir = None

    _workspace_class = workspace.Workspace
    def get_workspace(self):
        return self._workspace_class(self.output_dir, must_exist=False)

    def ident(self):
        return Action.ident(self) + '--' + (self.output_dir or '')    

    def log_filename(self):
        if self.output_dir is None: return None
        return os.path.join(self.output_dir, self.shell_name() + '_log.txt')


@Positional('working_dir', 'Directory for input and output files.')
class Action_with_working_dir(Action_with_log):
    working_dir = None
    
    _workspace_class = workspace.Workspace
    def get_workspace(self):
        return self._workspace_class(self.working_dir, must_exist=True)
    
    def ident(self):
        return Action.ident(self) + '--' + (self.working_dir or '')

    def log_filename(self):
        if self.working_dir is None: return None
        return os.path.join(self.working_dir, self.shell_name() + '_log.txt')



@String_flag('output', 'Output file (defaults to stdout). If filename ends with .gz or .bz2 it will be compressed appropriately.')
class Action_with_optional_output(Action):
    output = None
    
    def ident(self):
        return super(Action_with_optional_output,self).ident() + '--' + (self.output or '') 

    def begin_output(self):
        from nesoni import io
    
        if self.output is not None:
           return io.open_possibly_compressed_writer(self.output)
        else:
           return sys.stdout

    def end_output(self, f):
        if self.output is not None:
            f.close()

@String_flag('input', 'Input file (defaults to stdin). The file may be compressed with gzip or bzip2 or be a BAM file.')
class Action_with_optional_input(Action):
    input = None

    def begin_input(self):
        from nesoni import io    
        
        if self.input is not None:
           return io.open_possibly_compressed_file(self.input)
        else:
           return sys.stdin

    def end_input(self, f):
        if self.input is not None:
            f.close()

class Action_filter(Action_with_optional_input, Action_with_optional_output):
    pass




def report_exception():    
    exception = sys.exc_info()[1]
    
    brief = False
    for item in (Error, IOError):
        if isinstance(exception, item) and len(exception.args) > 0:
            brief = True
    
    if not brief:
        write_colored_text(sys.stderr, 
        '\n' + colored(2, 'Traceback:\n'+''.join(traceback.format_tb(sys.exc_info()[2]))))

    write_colored_text(sys.stderr, 
        '\n' + colored(1,colored(31, exception.__class__.__name__+':')) + '\n' + 
        colored(31, wrap(str(exception), 70, '    ')) + 
        '\n\n')


def shell_run(action, args, invocation=None):
    args = list(args)

    args_needed = False
    for item in action.parameters:
        if isinstance(item, Positional) or (isinstance(item, Section) and not item.empty_is_ok):
            args_needed = True

    if (args_needed and not args) or args == ['-h'] or args == ['--help']:
        write_colored_text(sys.stdout, 
            '\n'+action.describe(invocation, True)+'\n'+
            wrap(action.help, 70)+'\n\n\n'
        )
        sys.exit(1)        
    
    try:
        action.parse(args)
        write_colored_text(sys.stderr, '\n'+action.describe(invocation)+'\n')
        action.run()
    except:
        report_exception()
        sys.exit(1)





