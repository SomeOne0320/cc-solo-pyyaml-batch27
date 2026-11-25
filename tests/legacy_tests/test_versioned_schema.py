"""
Tests for the optional per-document version handling of the safe
load/dump entry points (yaml.safe_load, yaml.safe_load_all,
yaml.safe_dump, yaml.safe_dump_all).

Scenario: a configuration center receives YAML from legacy collectors
(YAML 1.1 rules: 'on' is a switch, '010' is octal) and from new
collectors (YAML 1.2 core schema: '0o10', '1e3', date-like ticket
numbers).  Documents declaring '%YAML 1.2' must be resolved with the
core schema while 1.1 or undeclared documents keep the legacy rules,
document by document, and values must round-trip through save-as.
"""

import unittest

import yaml

__all__ = ['TestPerDocumentVersionLoad', 'TestVersionedDumpRoundTrip',
        'TestLegacyChainIsolation']


# A realistic mixed-version document stream as received by the
# configuration center: one legacy collector document with an explicit
# 1.1 declaration, one undeclared (legacy) document, and one document
# from a new collector declaring YAML 1.2.
MIXED_STREAM = """\
%YAML 1.1
---
# legacy collector: 'on' is a switch, '010' is octal
switch: on
port: 010
---
# no directive: legacy rules apply
enabled: yes
retries: 3
%YAML 1.2
---
# new collector: YAML 1.2 core schema
switch: on
port: 010
mask: 0o10
ratio: 1e3
ticket: 2024-01-15
literal: !!str 1e3
quoted: "0o10"
'010': value-for-literal-key
on: value-for-on-key
"""

MIXED_DOCUMENTS = [
    {'switch': True, 'port': 8},
    {'enabled': True, 'retries': 3},
    {'switch': 'on', 'port': 10, 'mask': 8, 'ratio': 1000.0,
     'ticket': '2024-01-15', 'literal': '1e3', 'quoted': '0o10',
     '010': 'value-for-literal-key', 'on': 'value-for-on-key'},
]


class TestPerDocumentVersionLoad(unittest.TestCase):

    def test_auto_selects_schema_per_document(self):
        documents = list(yaml.safe_load_all(MIXED_STREAM, version='auto'))
        self.assertEqual(documents, MIXED_DOCUMENTS)

    def test_auto_keeps_legacy_rules_for_1_1_and_undeclared(self):
        stream = "%YAML 1.1\n---\na: on\n---\nb: 010\n"
        documents = list(yaml.safe_load_all(stream, version='auto'))
        self.assertEqual(documents, [{'a': True}, {'b': 8}])

    def test_auto_applies_core_schema_to_1_2_documents(self):
        document = yaml.safe_load(
                "%YAML 1.2\n---\nflag: on\noct: 0o10\nexp: 1e3\n",
                version='auto')
        self.assertEqual(document, {'flag': 'on', 'oct': 8, 'exp': 1000.0})

    def test_auto_switches_back_and_forth(self):
        # A 1.2 document between legacy documents must not leak its
        # rules into the following documents.
        stream = ("---\na: on\n"
                  "%YAML 1.2\n---\nb: on\n"
                  "---\nc: on\n"
                  "%YAML 1.2\n---\nd: on\n"
                  "---\ne: 010\n")
        documents = list(yaml.safe_load_all(stream, version='auto'))
        self.assertEqual(documents, [{'a': True}, {'b': 'on'}, {'c': True},
                {'d': 'on'}, {'e': 8}])

    def test_default_load_keeps_legacy_behavior(self):
        # Without the option, a %YAML 1.2 directive does not change
        # resolution: the legacy chain is untouched.
        stream = "%YAML 1.2\n---\nflag: on\nport: 010\nexp: 1e3\n"
        self.assertEqual(yaml.safe_load(stream),
                {'flag': True, 'port': 8, 'exp': '1e3'})
        self.assertEqual(yaml.safe_load(stream, version='1.1'),
                {'flag': True, 'port': 8, 'exp': '1e3'})

    def test_forced_version_ignores_directives(self):
        stream = "%YAML 1.2\n---\nflag: on\nmask: 0o10\n"
        self.assertEqual(yaml.safe_load(stream, version='1.1'),
                {'flag': True, 'mask': '0o10'})
        self.assertEqual(yaml.safe_load("flag: on\nmask: 0o10\n",
                version='1.2'), {'flag': 'on', 'mask': 8})

    def test_core_schema_scalar_forms(self):
        document = yaml.safe_load("""\
            yes_word: yes
            off_word: off
            dec: 10
            leading_zero: 010
            neg: -42
            oct: 0o10
            hex: 0x1F
            exp: 1e3
            exp_signed: +1.5E-3
            dot: .5
            trailing_dot: 5.
            inf: .inf
            nan: .nan
            true_word: true
            false_word: FALSE
            null_word: null
            tilde: ~
            date_like: 2024-01-15
            """, version='1.2')
        self.assertEqual(document['yes_word'], 'yes')
        self.assertEqual(document['off_word'], 'off')
        self.assertEqual(document['dec'], 10)
        self.assertEqual(document['leading_zero'], 10)
        self.assertIsInstance(document['leading_zero'], int)
        self.assertEqual(document['neg'], -42)
        self.assertEqual(document['oct'], 8)
        self.assertEqual(document['hex'], 31)
        self.assertEqual(document['exp'], 1000.0)
        self.assertIsInstance(document['exp'], float)
        self.assertEqual(document['exp_signed'], 0.0015)
        self.assertEqual(document['dot'], 0.5)
        self.assertEqual(document['trailing_dot'], 5.0)
        self.assertEqual(document['inf'], float('inf'))
        self.assertTrue(document['nan'] != document['nan'])
        self.assertIs(document['true_word'], True)
        self.assertIs(document['false_word'], False)
        self.assertIsNone(document['null_word'])
        self.assertIsNone(document['tilde'])
        self.assertEqual(document['date_like'], '2024-01-15')

    def test_explicit_tag_and_quotes_take_priority(self):
        # Explicit !!str tags and quoted scalars stay strings in both
        # schemas.
        for version in ('1.1', '1.2', 'auto'):
            document = yaml.safe_load(
                    "%YAML 1.2\n---\n"
                    "tagged: !!str on\n"
                    "single: '010'\n"
                    "double: \"1e3\"\n"
                    "tagged_int: !!str 0o10\n",
                    version=version)
            self.assertEqual(document, {'tagged': 'on', 'single': '010',
                    'double': '1e3', 'tagged_int': '0o10'},
                    "version=%r" % (version,))

    def test_explicit_yaml_tags_still_work(self):
        document = yaml.safe_load(
                "%YAML 1.2\n---\ni: !!int '42'\nb: !!bool 'true'\n",
                version='auto')
        self.assertEqual(document, {'i': 42, 'b': True})

    def test_nested_documents(self):
        document = yaml.safe_load(
                "%YAML 1.2\n"
                "---\n"
                "services:\n"
                "  - name: web\n"
                "    enabled: on\n"
                "    weight: 1e3\n"
                "  - name: db\n"
                "    ports: [010, 0o10]\n",
                version='auto')
        self.assertEqual(document, {'services': [
                {'name': 'web', 'enabled': 'on', 'weight': 1000.0},
                {'name': 'db', 'ports': [10, 8]}]})

    def test_empty_and_null_documents(self):
        self.assertEqual(list(yaml.safe_load_all("", version='auto')), [])
        self.assertIsNone(yaml.safe_load("", version='auto'))
        self.assertEqual(list(yaml.safe_load_all(
                "%YAML 1.2\n---\n---\n~\n", version='auto')), [None, None])

    def test_invalid_version_selector_rejected(self):
        for bad in ('2.0', '1.3', 'core', 12, (1, 2)):
            with self.assertRaises(ValueError):
                yaml.safe_load("a: 1\n", version=bad)
            with self.assertRaises(ValueError):
                list(yaml.safe_load_all("a: 1\n", version=bad))


class TestVersionedDumpRoundTrip(unittest.TestCase):

    def test_dump_writes_matching_directive(self):
        out = yaml.safe_dump({'a': 1}, version='1.2')
        self.assertTrue(out.startswith('%YAML 1.2\n---\n'), out)
        out = yaml.safe_dump({'a': 1}, version='1.1')
        self.assertTrue(out.startswith('%YAML 1.1\n---\n'), out)
        out = yaml.safe_dump({'a': 1})
        self.assertNotIn('%YAML', out)

    def test_dump_1_2_quotes_only_core_literals(self):
        out = yaml.safe_dump({
                'plain_on': 'on',          # plain string in 1.2 core
                'plain_date': '2024-01-15',  # no timestamp in core schema
                'looks_int': '010',
                'looks_oct': '0o10',
                'looks_exp': '1e3',
                'looks_bool': 'true',
                'looks_null': 'null',
                'switch': True,
                'ratio': 1000.0,
                }, version='1.2')
        self.assertIn('plain_on: on\n', out)
        self.assertIn('plain_date: 2024-01-15\n', out)
        self.assertIn("looks_int: '010'\n", out)
        self.assertIn("looks_oct: '0o10'\n", out)
        self.assertIn("looks_exp: '1e3'\n", out)
        self.assertIn("looks_bool: 'true'\n", out)
        self.assertIn("looks_null: 'null'\n", out)
        self.assertIn('switch: true\n', out)
        self.assertIn('ratio: 1000.0\n', out)

    def test_round_trip_scalars_and_keys(self):
        # Strings, numbers and booleans must come back with identical
        # types and values, including mapping keys and strings that
        # look like literals.
        data = {
            'on': 'on', '010': '010', '1e3': '1e3', '0o10': '0o10',
            'true': 'true', 'null': 'null', '~': '~',
            '2024-01-15': '2024-01-15', '': '',
            'bools': [True, False],
            'ints': [0, 7, -13, 10**20],
            'floats': [0.5, 1000.0, -2.5e-7, float('inf'), float('-inf')],
            'none': None,
            'nested': {'key_like_literal': {'1e3': ['0o10']}},
        }
        out = yaml.safe_dump(data, version='1.2')
        for read_version in ('auto', '1.2'):
            back = yaml.safe_load(out, version=read_version)
            self.assertEqual(back, data, "version=%r\n%s" % (read_version, out))
            for key in ('on', '010', '1e3', '0o10', 'true', 'null', '~',
                    '2024-01-15', ''):
                self.assertIsInstance(back[key], str)
            self.assertIsInstance(back['nested']['key_like_literal'], dict)

    def test_round_trip_nan(self):
        out = yaml.safe_dump({'nan': float('nan')}, version='1.2')
        back = yaml.safe_load(out, version='auto')
        self.assertTrue(back['nan'] != back['nan'])

    def test_round_trip_1_1(self):
        data = {'switch': True, 'port': 8, 'name': 'legacy',
                'literal': '1e3', 'word': 'on'}
        out = yaml.safe_dump(data, version='1.1')
        self.assertTrue(out.startswith('%YAML 1.1\n'), out)
        back = yaml.safe_load(out, version='auto')
        self.assertEqual(back, data)

    def test_mixed_stream_import_saveas_reimport(self):
        # Import a mixed-version stream, save every document with its
        # own version, then re-import: objects must be identical.
        documents = list(yaml.safe_load_all(MIXED_STREAM, version='auto'))
        self.assertEqual(documents, MIXED_DOCUMENTS)
        versions = ['1.1', None, '1.2']
        saved = ''.join(
                yaml.safe_dump(document, version=version, explicit_start=True)
                for document, version in zip(documents, versions))
        # The saved stream still declares each document's version.
        self.assertIn('%YAML 1.1\n', saved)
        self.assertIn('%YAML 1.2\n', saved)
        reimported = list(yaml.safe_load_all(saved, version='auto'))
        self.assertEqual(reimported, documents)

    def test_dump_all_single_version_stream(self):
        documents = [{'a': 'on'}, {'b': '1e3'}]
        out = yaml.safe_dump_all(documents, version='1.2')
        self.assertEqual(out.count('%YAML 1.2\n'), 2, out)
        back = list(yaml.safe_load_all(out, version='auto'))
        self.assertEqual(back, documents)

    def test_tuple_version_keeps_historical_meaning(self):
        # A (major, minor) tuple still only emits the directive without
        # changing scalar resolution: '1e3' stays unquoted, 'on' stays
        # quoted, exactly as the legacy chain produces.
        out = yaml.safe_dump({'exp': '1e3', 'word': 'on'}, version=(1, 2))
        self.assertTrue(out.startswith('%YAML 1.2\n'), out)
        self.assertIn('exp: 1e3\n', out)
        self.assertIn("word: 'on'\n", out)

    def test_invalid_version_selector_rejected(self):
        for bad in ('auto', '2.0', '1.3', 12, (1, 2, 3)):
            with self.assertRaises(ValueError):
                yaml.safe_dump({'a': 1}, version=bad)
            with self.assertRaises(ValueError):
                yaml.safe_dump_all([{'a': 1}], version=bad)


class TestLegacyChainIsolation(unittest.TestCase):

    def test_versioned_processing_does_not_leak(self):
        legacy_stream = "flag: on\nport: 010\nexp: 1e3\n"
        legacy_expected = {'flag': True, 'port': 8, 'exp': '1e3'}
        # Interleave versioned and legacy processing in one process.
        self.assertEqual(yaml.safe_load(legacy_stream), legacy_expected)
        self.assertEqual(yaml.safe_load(legacy_stream, version='1.2'),
                {'flag': 'on', 'port': 10, 'exp': 1000.0})
        self.assertEqual(yaml.safe_load(legacy_stream), legacy_expected)
        list(yaml.safe_load_all(MIXED_STREAM, version='auto'))
        self.assertEqual(yaml.safe_load(legacy_stream), legacy_expected)
        # The legacy dump chain is equally unaffected.
        legacy_dump = yaml.safe_dump({'exp': '1e3', 'word': 'on'})
        self.assertEqual(legacy_dump, "exp: 1e3\nword: 'on'\n")
        yaml.safe_dump({'exp': '1e3'}, version='1.2')
        self.assertEqual(yaml.safe_dump({'exp': '1e3', 'word': 'on'}),
                legacy_dump)

    def test_resolver_and_constructor_maps_are_isolated(self):
        # The new classes carry their own class-level maps; SafeLoader,
        # SafeDumper and Resolver are not mutated.
        from yaml.resolver import Resolver, CoreResolver
        self.assertIsNot(CoreResolver.yaml_implicit_resolvers,
                Resolver.yaml_implicit_resolvers)
        self.assertIs(yaml.SafeLoader.yaml_implicit_resolvers,
                Resolver.yaml_implicit_resolvers)
        self.assertIs(yaml.SafeDumper.yaml_implicit_resolvers,
                Resolver.yaml_implicit_resolvers)
        self.assertIs(yaml.CoreSafeDumper.yaml_implicit_resolvers,
                CoreResolver.yaml_implicit_resolvers)
        int_tag = 'tag:yaml.org,2002:int'
        self.assertIs(yaml.SafeLoader.yaml_constructors[int_tag],
                yaml.SafeLoader.construct_yaml_int)
        self.assertIsNot(
                yaml.VersionedSafeLoader.yaml_constructors[int_tag],
                yaml.SafeLoader.yaml_constructors[int_tag])
        # Other loaders keep working as before.
        self.assertEqual(yaml.full_load("flag: on\n"), {'flag': True})


if __name__ == '__main__':
    unittest.main()
