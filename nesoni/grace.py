
"""

Succeed or fail with good grace and manners. Play well with others.

"""

import sys, os, subprocess

from nesoni.config import Error, filesystem_friendly_name

class Help_shown(Exception):
    pass

def datum(sample_name, field, value):        
    return '(> %s %s %s' % (sample_name, pretty_number(value, 12), field)

class Log:
    def __init__(self):
        self.text = [ ]
        self.f = None
    
    def attach(self, f):
        assert not self.f
        self.f = f
        self.f.write(''.join(self.text))
        self.f.flush()
    
    def close(self):
        if self.f is not None:
            self.f.close()
            self.f = None
    
    def log(self, text):
        sys.stderr.write(text)
        self.quietly_log(text)

    def datum(self, sample_name, field, value):        
        self.log(datum(sample_name, field, value) + '\n')

    def quietly_log(self, text):        
        self.text.append(text)
        if self.f:
           self.f.write(text)
           self.f.flush()
    


def status(string):
    """ Display a status string. """
    from nesoni import legion
    legion.coordinator().set_status( legion.process_identity(), string )
    #if sys.stderr.isatty():
    #    #Show in terminal title
    #    sys.stderr.write('\x1b]2;'+string+'\x07')
    #    sys.stderr.flush()
    #    
    #    #sys.stderr.write('\r\x1b[K\x1b[34m' + string + '\x1b[m\r')
    #    #sys.stderr.flush()

def load(module_name):
    status('Loading')
    m = __import__(module_name, globals())
    status('')
    return m


def pretty_number(number, width=0):
    """ Adds commas for readability. """
    if isinstance(number, float):
        result = '%.3f' % number
    else:
        assert isinstance(number,int)    
        s = str(abs(number))[::-1]
        groups = [ s[i:i+3] for i in xrange(0,len(s),3) ]
        result = ','.join(groups)
        if number < 0: 
            result += '-'
        result = result[::-1]
    if len(result) < width:
        result = ' '*(width-len(result)) + result
    return result

def word_wrap(text, width):
    return reduce(lambda line, word, width=width: '%s%s%s' %
                  (line,
                   ' \n'[(len(line)-line.rfind('\n')-1
                         + len(word.split('\n',1)[0]
                              ) >= width)],
                   word),
                  text.split(' ')
                 )

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

def get_option_value(args, option, conversion_function, default, log=None, displayer='%s', description=''):
    """ Get a command line option """
    args = args[:]
    value = default
    while True:
        try:
            location = args.index(option)
        except ValueError: #Not found
            break
            
        if location == len(args)-1 :
            raise Error('Option %s requires a paramter' % option)
        
        try:
            value = conversion_function(args[location+1])
        except Exception:
            raise Error('Option for %s not in expected format' % option)
        
        del args[location:location+2]

    if log:
        if isinstance(displayer, str):
            display = displayer % value
        else:
            display = displayer(value)
        log.log('%18s %-8s - %s\n' % (option, display, word_wrap(description,49).replace('\n','\n'+' '*30)))         

    return value, args


def get_flag(argv, flag):
    argv = argv[:]
    any = False
    while True:
        try:
            location = argv.index(flag)
            any = True
        except ValueError: #Not found
            break
        
        del argv[location]
    return any, argv

def expect_no_further_options(args):
    for arg in args:
        if arg.startswith('-'):
            raise Error('Unexpected flag "%s"' % arg)



def default_command(args):
    if args:
        raise Error('Don\'t know what to do with %s' % (' '.join(args)))
    
def execute(args, commands, default_command=default_command):
    """ Execute a series of commands specified on the command line.
        
        eg
        [default comman param] command: [param ...] command: [param ...]
    
        An older format is also supported:
        eg
        [default command param] command [param ...] command [param ...]
        (deprecated, filenames can collide with command names without the ":" decoration)
        
    """
    
    if not isinstance(commands, dict):
        commands = dict( (item.__name__.replace('_','-').strip('-'), item) for item in commands )
    
    if any( item.endswith(':') and item[:-1] in commands for item in args ):
        commands = dict( (a+':',b) for a,b in commands.items() )
    
    command_locations = [ i for i,arg in enumerate(args) if arg in commands ]
    split_points = command_locations + [len(args)]    
    
    #if split_points[0] != 0:
    default_command(args[:split_points[0]])
    
    for start, end in zip(command_locations, split_points[1:]):
        commands[args[start]](args[start+1:end])


def how_many_cpus():
    """Detects the number of effective CPUs in the system,
    
       Function nicked from Parallel Python."""
    #for Linux, Unix and MacOS
    try:
        if hasattr(os, "sysconf"):
            if os.sysconf_names.has_key("SC_NPROCESSORS_ONLN"): 
                #Linux and Unix
                ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
                if isinstance(ncpus, int) and ncpus > 0:
                    return ncpus
            else: 
                #MacOS X
                return int(os.popen2("sysctl -n hw.ncpu")[1].read())
        #for Windows
        if os.environ.has_key("NUMBER_OF_PROCESSORS"):
            ncpus = int(os.environ["NUMBER_OF_PROCESSORS"]);
            if ncpus > 0:
                return ncpus
    except:
        print >> sys.stderr, 'Attempt to determine number of CPUs failed, defaulting to 1'
    #return the default value
    return 1


def require_shrimp_1():
    try:
        text = subprocess.Popen(['rmapper-ls'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[1]
    except OSError:
        raise Error("Couldn't run 'rmapper-ls'. SHRiMP 1 not installed?")

def get_shrimp_2_version():
    try:
        text = subprocess.Popen(['gmapper-ls'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[1]
    except OSError:
        raise Error("Couldn't run 'gmapper-ls'. SHRiMP 2 not installed?")

    for line in text.split('\n'):
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] == 'SHRiMP':
            return parts[1]

    raise Error("gmapper-ls didn't output a version number as expected")

def require_shrimp_2():
    version = get_shrimp_2_version()
    version_parts = version.split('.')
    major = int(version_parts[0])
    minor = int(version_parts[1])
    if major < 2 or (major == 2 and minor < 1):
        raise Error("SHRiMP version 2.1 or higher required")

def require_samtools():
    try:
        text = subprocess.Popen(['samtools'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[1]
    except OSError:
        raise Error("Couldn't run 'samtools'. Not installed?")

def require_sff2fastq():
    try:
        text = subprocess.Popen(['sff2fastq'], stdout=subprocess.PIPE, stderr=subprocess.PIPE).communicate()[1]
    except OSError:
        raise Error("Couldn't run 'sff2fastq'. Not installed?")


