
import gc
import io

import yaml


class NonSeekableStream:
    """A stream that only exposes fixed-size chunks and cannot be rewound."""

    def __init__(self, data, chunk_size=16):
        self.buffer = data
        self.position = 0
        self.chunk_size = chunk_size
        self.read_count = 0
        self.closed_by_loader = False

    def read(self, size=-1):
        self.read_count += 1
        if size is None or size < 0:
            size = self.chunk_size
        size = min(size, self.chunk_size)
        end = self.position + size
        part = self.buffer[self.position:end]
        self.position = end
        return part

    def close(self):
        self.closed_by_loader = True


def test_load_iter_matches_safe_load(verbose=False):
    document = (
        "- id: 1\n"
        "  name: alpha\n"
        "- id: 2\n"
        "  nested:\n"
        "    - 1\n"
        "    - 2\n"
        "- id: 3\n"
        "  tags: !!set\n"
        "    a: null\n"
        "    b: null\n"
        "- merged:\n"
        "    <<: {a: 1, b: 2}\n"
        "    b: 3\n"
    )
    expected = yaml.safe_load(document)
    for stream in (document, io.StringIO(document),
                   io.BytesIO(document.encode('utf-8'))):
        result = list(yaml.safe_load_iter(stream))
        assert result == expected, (result, expected)

test_load_iter_matches_safe_load.unittest = True


def test_load_iter_first_record_before_whole_stream_consumed(verbose=False):
    document = "".join("- record %d\n" % index for index in range(100))
    stream = NonSeekableStream(document.encode('utf-8'))
    iterator = yaml.load_iter(stream, yaml.SafeLoader)
    first = next(iterator)
    assert first == "record 0"
    # Only the chunks needed to build the first record may have been read.
    assert stream.position < len(stream.buffer), (
            stream.position, len(stream.buffer))
    assert list(iterator) == ["record %d" % index for index in range(1, 100)]

test_load_iter_first_record_before_whole_stream_consumed.unittest = True


def test_load_iter_forward_anchor_identity(verbose=False):
    document = (
        "- &config {host: localhost, port: 5432}\n"
        + "".join("- item %d\n" % index for index in range(50))
        + "- use: *config\n"
    )
    records = list(yaml.safe_load_iter(io.StringIO(document)))
    assert records[0] == {"host": "localhost", "port": 5432}
    assert records[-1]["use"] is records[0]

test_load_iter_forward_anchor_identity.unittest = True


def test_load_iter_aliases_and_self_references(verbose=False):
    document = (
        "- &rec\n"
        "  name: rec\n"
        "  self: *rec\n"
        "- list: &seq\n"
        "  - 1\n"
        "  - 2\n"
        "  back: *seq\n"
    )
    records = list(yaml.safe_load_iter(io.StringIO(document)))
    assert records[0]["self"] is records[0]
    assert records[0]["name"] == "rec"
    assert records[1]["back"] is records[1]["list"]
    assert records[1]["list"] == [1, 2]
    # The regular whole-document loader must build the same identities.
    reference = yaml.safe_load(document)
    assert reference[0]["self"] is reference[0]
    assert reference[1]["back"] is reference[1]["list"]

test_load_iter_aliases_and_self_references.unittest = True


def test_load_iter_self_referential_root_sequence(verbose=False):
    # An anchor on the root sequence itself requires whole-document fallback
    # so that aliases pointing back at the container keep working; the
    # iterator then yields the whole container as its single record.
    document = (
        "&root\n"
        "- name: first\n"
        "- back: *root\n"
    )
    records = list(yaml.safe_load_iter(io.StringIO(document)))
    assert len(records) == 1
    root = records[0]
    assert root[0] == {"name": "first"}
    assert root[1]["back"] is root
    reference = yaml.safe_load(document)
    assert reference[1]["back"] is reference

test_load_iter_self_referential_root_sequence.unittest = True


def test_load_iter_bounded_memory(verbose=False):
    class Marker:
        def __init__(self, number):
            self.number = number

    class MarkerLoader(yaml.SafeLoader):
        pass

    MarkerLoader.add_constructor(
            '!marker',
            lambda loader, node: Marker(int(loader.construct_scalar(node))))

    def live_markers():
        gc.collect()
        return sum(1 for obj in gc.get_objects() if isinstance(obj, Marker))

    def consume(count):
        document = "".join("- !marker %d\n" % index for index in range(count))
        for record in yaml.load_iter(io.StringIO(document), MarkerLoader):
            del record

    consume(25)
    baseline = live_markers()
    consume(400)
    assert live_markers() == baseline, (live_markers(), baseline)
    assert baseline == 0

test_load_iter_bounded_memory.unittest = True


def test_load_iter_keeps_anchored_records(verbose=False):
    class Marker:
        def __init__(self, number):
            self.number = number

    class MarkerLoader(yaml.SafeLoader):
        pass

    MarkerLoader.add_constructor(
            '!marker',
            lambda loader, node: Marker(int(loader.construct_scalar(node))))

    def count_markers():
        gc.collect()
        return sum(1 for obj in gc.get_objects() if isinstance(obj, Marker))

    document = ("- &kept !marker 0\n"
                + "".join("- !marker %d\n" % index for index in range(1, 60)))
    iterator = yaml.load_iter(io.StringIO(document), MarkerLoader)
    anchored = next(iterator)
    probes = []
    for index, record in enumerate(iterator):
        del record
        if index % 20 == 0:
            probes.append(count_markers())
    # One current record plus the anchored config; never the whole history.
    assert probes == [2, 2, 2], probes
    del iterator
    gc.collect()
    assert count_markers() == 1  # the caller still holds `anchored`
    assert anchored.number == 0

test_load_iter_keeps_anchored_records.unittest = True


def test_load_iter_error_after_delivered_records(verbose=False):
    document = "- ok: 1\n- ok: 2\n- broken: [unterminated\n"
    iterator = yaml.safe_load_iter(io.StringIO(document))
    assert next(iterator) == {"ok": 1}
    assert next(iterator) == {"ok": 2}
    try:
        next(iterator)
    except yaml.YAMLError as exc:
        if verbose:
            print("%s: %s" % (exc.__class__.__name__, exc))
    else:
        raise AssertionError("expected a YAMLError")

test_load_iter_error_after_delivered_records.unittest = True


def test_load_iter_early_close_stops_reading(verbose=False):
    document = "".join("- record %d\n" % index for index in range(50))
    stream = NonSeekableStream(document.encode('utf-8'))
    iterator = yaml.safe_load_iter(stream)
    next(iterator)
    iterator.close()
    position_after_close = stream.position
    reads_after_close = stream.read_count
    # Closing the iterator must not touch the stream again.
    assert stream.position == position_after_close
    assert stream.read_count == reads_after_close
    assert not stream.closed_by_loader
    # The caller still owns the stream and can read the remainder themselves.
    remainder = stream.buffer[stream.position:]
    assert b"record 49" in remainder

test_load_iter_early_close_stops_reading.unittest = True


def test_load_iter_does_not_close_callers_stream(verbose=False):
    stream = NonSeekableStream(b"- 1\n- 2\n- 3\n")
    list(yaml.safe_load_iter(stream))
    assert not stream.closed_by_loader

test_load_iter_does_not_close_callers_stream.unittest = True


def test_load_iter_non_sequence_roots(verbose=False):
    assert list(yaml.safe_load_iter(io.StringIO("just a scalar\n"))) == [
            "just a scalar"]
    assert list(yaml.safe_load_iter(io.StringIO("a: 1\nb: 2\n"))) == [
            {"a": 1, "b": 2}]
    assert list(yaml.safe_load_iter(io.StringIO(""))) == []

test_load_iter_non_sequence_roots.unittest = True


def test_load_iter_rejects_libyaml_loaders(verbose=False):
    if not yaml.__with_libyaml__:
        if verbose:
            print("libyaml extension not available; skipping")
        return
    try:
        list(yaml.load_iter(io.StringIO("- 1\n"), yaml.CSafeLoader))
    except TypeError as exc:
        if verbose:
            print(exc)
    else:
        raise AssertionError("expected TypeError for the libyaml loader")

test_load_iter_rejects_libyaml_loaders.unittest = True


if __name__ == '__main__':
    import test_appliance
    test_appliance.run(globals())
