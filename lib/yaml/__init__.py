
from .error import *

from .tokens import *
from .events import *
from .nodes import *

from .loader import *
from .dumper import *

__version__ = '6.0.3'
try:
    from .cyaml import *
    __with_libyaml__ = True
except ImportError:
    __with_libyaml__ = False

import io

#------------------------------------------------------------------------------
# XXX "Warnings control" is now deprecated. Leaving in the API function to not
# break code that uses it.
#------------------------------------------------------------------------------
def warnings(settings=None):
    if settings is None:
        return {}

#------------------------------------------------------------------------------
def scan(stream, Loader=Loader):
    """
    Scan a YAML stream and produce scanning tokens.
    """
    loader = Loader(stream)
    try:
        while loader.check_token():
            yield loader.get_token()
    finally:
        loader.dispose()

def parse(stream, Loader=Loader):
    """
    Parse a YAML stream and produce parsing events.
    """
    loader = Loader(stream)
    try:
        while loader.check_event():
            yield loader.get_event()
    finally:
        loader.dispose()

def compose(stream, Loader=Loader):
    """
    Parse the first YAML document in a stream
    and produce the corresponding representation tree.
    """
    loader = Loader(stream)
    try:
        return loader.get_single_node()
    finally:
        loader.dispose()

def compose_all(stream, Loader=Loader):
    """
    Parse all YAML documents in a stream
    and produce corresponding representation trees.
    """
    loader = Loader(stream)
    try:
        while loader.check_node():
            yield loader.get_node()
    finally:
        loader.dispose()

def load(stream, Loader):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.
    """
    loader = Loader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()

def load_all(stream, Loader):
    """
    Parse all YAML documents in a stream
    and produce corresponding Python objects.
    """
    loader = Loader(stream)
    try:
        while loader.check_data():
            yield loader.get_data()
    finally:
        loader.dispose()

def full_load(stream):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.

    Resolve all tags except those known to be
    unsafe on untrusted input.
    """
    return load(stream, FullLoader)

def full_load_all(stream):
    """
    Parse all YAML documents in a stream
    and produce corresponding Python objects.

    Resolve all tags except those known to be
    unsafe on untrusted input.
    """
    return load_all(stream, FullLoader)

def _safe_loader_for_version(version):
    """
    Return the SafeLoader variant matching the requested version handling:
    None or '1.1' keeps the legacy YAML 1.1 rules, '1.2' forces the
    YAML 1.2 core schema for the whole stream, and 'auto' selects the
    schema of each document from its %YAML directive.
    """
    if version is None or version == '1.1':
        return SafeLoader
    elif version == '1.2':
        return CoreSafeLoader
    elif version == 'auto':
        return VersionedSafeLoader
    else:
        raise ValueError("unsupported YAML version selector: %r "
                "(expected None, 'auto', '1.1' or '1.2')" % (version,))

def safe_load(stream, version=None):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.

    Resolve only basic YAML tags. This is known
    to be safe for untrusted input.

    The optional version argument selects how scalar types are resolved:
    with 'auto', each document follows its %YAML directive (YAML 1.2
    documents use the core schema, YAML 1.1 or undeclared documents keep
    the legacy rules); '1.1' or '1.2' force one schema for the whole
    stream.  The default (None) keeps the legacy behavior.
    """
    return load(stream, _safe_loader_for_version(version))

def safe_load_all(stream, version=None):
    """
    Parse all YAML documents in a stream
    and produce corresponding Python objects.

    Resolve only basic YAML tags. This is known
    to be safe for untrusted input.

    The optional version argument selects how scalar types are resolved:
    with 'auto', each document follows its %YAML directive (YAML 1.2
    documents use the core schema, YAML 1.1 or undeclared documents keep
    the legacy rules); '1.1' or '1.2' force one schema for the whole
    stream.  The default (None) keeps the legacy behavior.
    """
    return load_all(stream, _safe_loader_for_version(version))

def unsafe_load(stream):
    """
    Parse the first YAML document in a stream
    and produce the corresponding Python object.

    Resolve all tags, even those known to be
    unsafe on untrusted input.
    """
    return load(stream, UnsafeLoader)

def unsafe_load_all(stream):
    """
    Parse all YAML documents in a stream
    and produce corresponding Python objects.

    Resolve all tags, even those known to be
    unsafe on untrusted input.
    """
    return load_all(stream, UnsafeLoader)

def emit(events, stream=None, Dumper=Dumper,
        canonical=None, indent=None, width=None,
        allow_unicode=None, line_break=None):
    """
    Emit YAML parsing events into a stream.
    If stream is None, return the produced string instead.
    """
    getvalue = None
    if stream is None:
        stream = io.StringIO()
        getvalue = stream.getvalue
    dumper = Dumper(stream, canonical=canonical, indent=indent, width=width,
            allow_unicode=allow_unicode, line_break=line_break)
    try:
        for event in events:
            dumper.emit(event)
    finally:
        dumper.dispose()
    if getvalue:
        return getvalue()

def serialize_all(nodes, stream=None, Dumper=Dumper,
        canonical=None, indent=None, width=None,
        allow_unicode=None, line_break=None,
        encoding=None, explicit_start=None, explicit_end=None,
        version=None, tags=None):
    """
    Serialize a sequence of representation trees into a YAML stream.
    If stream is None, return the produced string instead.
    """
    getvalue = None
    if stream is None:
        if encoding is None:
            stream = io.StringIO()
        else:
            stream = io.BytesIO()
        getvalue = stream.getvalue
    dumper = Dumper(stream, canonical=canonical, indent=indent, width=width,
            allow_unicode=allow_unicode, line_break=line_break,
            encoding=encoding, version=version, tags=tags,
            explicit_start=explicit_start, explicit_end=explicit_end)
    try:
        dumper.open()
        for node in nodes:
            dumper.serialize(node)
        dumper.close()
    finally:
        dumper.dispose()
    if getvalue:
        return getvalue()

def serialize(node, stream=None, Dumper=Dumper, **kwds):
    """
    Serialize a representation tree into a YAML stream.
    If stream is None, return the produced string instead.
    """
    return serialize_all([node], stream, Dumper=Dumper, **kwds)

def dump_all(documents, stream=None, Dumper=Dumper,
        default_style=None, default_flow_style=False,
        canonical=None, indent=None, width=None,
        allow_unicode=None, line_break=None,
        encoding=None, explicit_start=None, explicit_end=None,
        version=None, tags=None, sort_keys=True):
    """
    Serialize a sequence of Python objects into a YAML stream.
    If stream is None, return the produced string instead.
    """
    getvalue = None
    if stream is None:
        if encoding is None:
            stream = io.StringIO()
        else:
            stream = io.BytesIO()
        getvalue = stream.getvalue
    dumper = Dumper(stream, default_style=default_style,
            default_flow_style=default_flow_style,
            canonical=canonical, indent=indent, width=width,
            allow_unicode=allow_unicode, line_break=line_break,
            encoding=encoding, version=version, tags=tags,
            explicit_start=explicit_start, explicit_end=explicit_end, sort_keys=sort_keys)
    try:
        dumper.open()
        for data in documents:
            dumper.represent(data)
        dumper.close()
    finally:
        dumper.dispose()
    if getvalue:
        return getvalue()

def dump(data, stream=None, Dumper=Dumper, **kwds):
    """
    Serialize a Python object into a YAML stream.
    If stream is None, return the produced string instead.
    """
    return dump_all([data], stream, Dumper=Dumper, **kwds)

def safe_dump_all(documents, stream=None, version=None, **kwds):
    """
    Serialize a sequence of Python objects into a YAML stream.
    Produce only basic YAML tags.
    If stream is None, return the produced string instead.

    The optional version argument selects the schema used to decide
    which scalars need quoting: with '1.1' or '1.2' the matching %YAML
    directive is written and scalars are quoted so that reading the
    output back under the same version (or version='auto' on load)
    preserves the type and value of every scalar, including mapping
    keys.  A (major, minor) tuple keeps the historical meaning: the
    directive is emitted but scalar resolution is unchanged.  The
    default (None) keeps the legacy behavior.
    """
    if isinstance(version, str):
        if version == '1.1':
            return dump_all(documents, stream, Dumper=SafeDumper,
                    version=(1, 1), **kwds)
        elif version == '1.2':
            return dump_all(documents, stream, Dumper=CoreSafeDumper,
                    version=(1, 2), **kwds)
        else:
            raise ValueError("unsupported YAML version selector: %r "
                    "(expected None, '1.1', '1.2' or a (major, minor) tuple)"
                    % (version,))
    if version is not None:
        if not (isinstance(version, (tuple, list)) and len(version) == 2
                and all(isinstance(part, int) for part in version)):
            raise ValueError("unsupported YAML version selector: %r "
                    "(expected None, '1.1', '1.2' or a (major, minor) tuple)"
                    % (version,))
        version = tuple(version)
    return dump_all(documents, stream, Dumper=SafeDumper, version=version, **kwds)

def safe_dump(data, stream=None, version=None, **kwds):
    """
    Serialize a Python object into a YAML stream.
    Produce only basic YAML tags.
    If stream is None, return the produced string instead.

    See safe_dump_all for the meaning of the optional version argument.
    """
    return safe_dump_all([data], stream, version=version, **kwds)

def add_implicit_resolver(tag, regexp, first=None,
        Loader=None, Dumper=Dumper):
    """
    Add an implicit scalar detector.
    If an implicit scalar value matches the given regexp,
    the corresponding tag is assigned to the scalar.
    first is a sequence of possible initial characters or None.
    """
    if Loader is None:
        loader.Loader.add_implicit_resolver(tag, regexp, first)
        loader.FullLoader.add_implicit_resolver(tag, regexp, first)
        loader.UnsafeLoader.add_implicit_resolver(tag, regexp, first)
    else:
        Loader.add_implicit_resolver(tag, regexp, first)
    Dumper.add_implicit_resolver(tag, regexp, first)

def add_path_resolver(tag, path, kind=None, Loader=None, Dumper=Dumper):
    """
    Add a path based resolver for the given tag.
    A path is a list of keys that forms a path
    to a node in the representation tree.
    Keys can be string values, integers, or None.
    """
    if Loader is None:
        loader.Loader.add_path_resolver(tag, path, kind)
        loader.FullLoader.add_path_resolver(tag, path, kind)
        loader.UnsafeLoader.add_path_resolver(tag, path, kind)
    else:
        Loader.add_path_resolver(tag, path, kind)
    Dumper.add_path_resolver(tag, path, kind)

def add_constructor(tag, constructor, Loader=None):
    """
    Add a constructor for the given tag.
    Constructor is a function that accepts a Loader instance
    and a node object and produces the corresponding Python object.
    """
    if Loader is None:
        loader.Loader.add_constructor(tag, constructor)
        loader.FullLoader.add_constructor(tag, constructor)
        loader.UnsafeLoader.add_constructor(tag, constructor)
    else:
        Loader.add_constructor(tag, constructor)

def add_multi_constructor(tag_prefix, multi_constructor, Loader=None):
    """
    Add a multi-constructor for the given tag prefix.
    Multi-constructor is called for a node if its tag starts with tag_prefix.
    Multi-constructor accepts a Loader instance, a tag suffix,
    and a node object and produces the corresponding Python object.
    """
    if Loader is None:
        loader.Loader.add_multi_constructor(tag_prefix, multi_constructor)
        loader.FullLoader.add_multi_constructor(tag_prefix, multi_constructor)
        loader.UnsafeLoader.add_multi_constructor(tag_prefix, multi_constructor)
    else:
        Loader.add_multi_constructor(tag_prefix, multi_constructor)

def add_representer(data_type, representer, Dumper=Dumper):
    """
    Add a representer for the given type.
    Representer is a function accepting a Dumper instance
    and an instance of the given data type
    and producing the corresponding representation node.
    """
    Dumper.add_representer(data_type, representer)

def add_multi_representer(data_type, multi_representer, Dumper=Dumper):
    """
    Add a representer for the given type.
    Multi-representer is a function accepting a Dumper instance
    and an instance of the given data type or subtype
    and producing the corresponding representation node.
    """
    Dumper.add_multi_representer(data_type, multi_representer)

class YAMLObjectMetaclass(type):
    """
    The metaclass for YAMLObject.
    """
    def __init__(cls, name, bases, kwds):
        super(YAMLObjectMetaclass, cls).__init__(name, bases, kwds)
        if 'yaml_tag' in kwds and kwds['yaml_tag'] is not None:
            if isinstance(cls.yaml_loader, list):
                for loader in cls.yaml_loader:
                    loader.add_constructor(cls.yaml_tag, cls.from_yaml)
            else:
                cls.yaml_loader.add_constructor(cls.yaml_tag, cls.from_yaml)

            cls.yaml_dumper.add_representer(cls, cls.to_yaml)

class YAMLObject(metaclass=YAMLObjectMetaclass):
    """
    An object that can dump itself to a YAML stream
    and load itself from a YAML stream.
    """

    __slots__ = ()  # no direct instantiation, so allow immutable subclasses

    yaml_loader = [Loader, FullLoader, UnsafeLoader]
    yaml_dumper = Dumper

    yaml_tag = None
    yaml_flow_style = None

    @classmethod
    def from_yaml(cls, loader, node):
        """
        Convert a representation node to a Python object.
        """
        return loader.construct_yaml_object(node, cls)

    @classmethod
    def to_yaml(cls, dumper, data):
        """
        Convert a Python object to a representation node.
        """
        return dumper.represent_yaml_object(cls.yaml_tag, data, cls,
                flow_style=cls.yaml_flow_style)

