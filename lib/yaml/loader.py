
__all__ = ['BaseLoader', 'FullLoader', 'SafeLoader', 'Loader', 'UnsafeLoader',
        'CoreSafeLoader', 'VersionedSafeLoader']

from .reader import *
from .scanner import *
from .parser import *
from .composer import *
from .constructor import *
from .resolver import *

class BaseLoader(Reader, Scanner, Parser, Composer, BaseConstructor, BaseResolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        BaseConstructor.__init__(self)
        BaseResolver.__init__(self)

class FullLoader(Reader, Scanner, Parser, Composer, FullConstructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        FullConstructor.__init__(self)
        Resolver.__init__(self)

class SafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)

class Loader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)

# UnsafeLoader is the same as Loader (which is and was always unsafe on
# untrusted input). Use of either Loader or UnsafeLoader should be rare, since
# FullLoad should be able to load almost all YAML safely. Loader is left intact
# to ensure backwards compatibility.
class UnsafeLoader(Reader, Scanner, Parser, Composer, Constructor, Resolver):

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        Constructor.__init__(self)
        Resolver.__init__(self)

class CoreSafeLoader(Reader, Scanner, Parser, Composer, CoreConstructor, CoreResolver):
    """
    A SafeLoader that resolves and constructs every document in the
    stream with the YAML 1.2 core schema, regardless of whether the
    documents carry a %YAML directive.
    """

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        CoreConstructor.__init__(self)
        CoreResolver.__init__(self)

class VersionedSafeLoader(Reader, Scanner, Parser, Composer, SafeConstructor, Resolver):
    """
    A SafeLoader that selects the resolution schema per document:
    documents opened with a '%YAML 1.2' (or later 1.x) directive are
    resolved with the YAML 1.2 core schema, all other documents
    (including documents without any directive) with the legacy
    YAML 1.1 rules.  Explicit tags and quoted scalars are never
    affected by the switch.
    """

    def __init__(self, stream):
        Reader.__init__(self, stream)
        Scanner.__init__(self)
        Parser.__init__(self)
        Composer.__init__(self)
        SafeConstructor.__init__(self)
        Resolver.__init__(self)
        self._core_schema_document = False

    def compose_document(self):
        # Inspect the version of the DOCUMENT-START event and switch
        # the implicit resolvers for the duration of this document.
        # The instance attribute shadows the class-level resolver map,
        # so no other loader is affected.
        version = self.peek_event().version
        if version is not None and tuple(version) >= (1, 2):
            self.yaml_implicit_resolvers = CoreResolver.yaml_implicit_resolvers
            self._core_schema_document = True
        else:
            self.yaml_implicit_resolvers = type(self).yaml_implicit_resolvers
            self._core_schema_document = False
        return super().compose_document()

    def construct_yaml_int(self, node):
        # Integer literals are parsed according to the schema of the
        # document that is currently being constructed; construction of
        # a document always completes before the next one is composed.
        if self._core_schema_document:
            return CoreConstructor.construct_yaml_int(self, node)
        return SafeConstructor.construct_yaml_int(self, node)

VersionedSafeLoader.add_constructor(
        'tag:yaml.org,2002:int',
        VersionedSafeLoader.construct_yaml_int)
