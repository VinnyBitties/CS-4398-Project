"""Bounded static CLI header/declared-table measurements; never loads assemblies.

Definitions: ECMA-335 II.24.2, II.25.3.3 and Microsoft's IMAGE_COR20_HEADER.
https://ecma-international.org/wp-content/uploads/ECMA-335_6th_edition_june_2012.pdf
These are declared metadata counts, not validated IL, managed API calls or trust.
"""
import hashlib
from pathlib import Path
import struct

SCHEMA = 'cfd-cli-declared-metadata-v1'
EXTRACTOR_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def inspect(data, pe):
    result = {'schema_version': SCHEMA, 'extractor_sha256': EXTRACTOR_SHA256,
              'sha256': hashlib.sha256(data).hexdigest(), 'status': 'unavailable',
              'present': None, 'metadata_bytes': None, 'type_ref_rows': None, 'method_def_rows': None}
    def require(ok, message):
        if not ok: raise ValueError(message)
    def rva_bytes(rva, size):
        require(type(rva) is int and type(size) is int and 0 < size <= len(data), 'invalid_rva_size')
        section = pe.get_section_by_rva(rva)
        require(section is not None and section.VirtualAddress <= rva and
                rva + size <= section.VirtualAddress + section.SizeOfRawData, 'rva_not_fully_backed')
        offset = int(section.PointerToRawData) + rva - int(section.VirtualAddress)
        require(0 <= offset <= len(data)-size, 'truncated_rva')
        return data[offset:offset+size]
    try:
        directories = pe.OPTIONAL_HEADER.DATA_DIRECTORY
        require(pe.OPTIONAL_HEADER.NumberOfRvaAndSizes <= len(directories), 'truncated_directories')
        if len(directories) <= 14 or (directories[14].VirtualAddress == 0 and directories[14].Size == 0):
            result.update(status='complete', present=False, metadata_bytes=0, type_ref_rows=0, method_def_rows=0)
            return result
        directory = directories[14]
        require(directory.Size >= 72 and directory.VirtualAddress > 0, 'invalid_cli_directory')
        header = rva_bytes(int(directory.VirtualAddress), 72)
        require(struct.unpack_from('<I', header)[0] >= 72, 'invalid_cli_header')
        rva, size = struct.unpack_from('<II', header, 8)
        metadata = rva_bytes(rva, size)
        require(len(metadata) >= 20 and metadata[:4] == b'BSJB', 'invalid_metadata_root')
        version_length = struct.unpack_from('<I', metadata, 12)[0]
        require(0 < version_length <= 256 and version_length % 4 == 0 and 20+version_length <= size, 'invalid_version_span')
        position = 16+version_length
        flags, count = struct.unpack_from('<HH', metadata, position); position += 4
        require(flags == 0 and 0 < count <= 16, 'unsupported_stream_header')
        streams = {}
        for _ in range(count):
            require(position+9 <= size, 'truncated_stream_header')
            offset, length = struct.unpack_from('<II', metadata, position); position += 8
            nul = metadata.find(b'\0', position, min(size, position+33))
            require(nul >= position, 'invalid_stream_name')
            name = metadata[position:nul].decode('ascii'); position = (nul+4)//4*4
            require(name not in streams and 0 <= offset <= size-length and length >= 0, 'invalid_stream_bounds')
            streams[name] = (offset, length)
        nonempty = sorted((a,a+n) for a,n in streams.values() if n)
        require(all(a >= position for a,z in nonempty) and
                all(z <= a2 for (_,z),(a2,_) in zip(nonempty,nonempty[1:])), 'overlapping_metadata_streams')
        tables = [streams[k] for k in ('#~','#-') if k in streams]
        require(len(tables) == 1, 'missing_or_ambiguous_tables')
        offset, length = tables[0]; require(length >= 24, 'truncated_tables_header')
        reserved, major, minor, heaps, pad, valid, sorted_mask = struct.unpack_from('<IBBBBQQ', metadata, offset)
        require(reserved == 0 and major == 2 and minor == 0 and pad == 1 and heaps & ~7 == 0, 'unsupported_tables_version')
        position = offset+24; counts = {}
        for table in range(64):
            if valid & (1 << table):
                require(position+4 <= offset+length, 'truncated_row_counts')
                rows = struct.unpack_from('<I', metadata, position)[0]; position += 4
                require(rows <= length, 'impossible_declared_row_count')
                counts[table] = rows
        require(sum(counts.values()) <= offset+length-position, 'row_counts_exceed_table_bytes')
        result.update(status='complete', present=True, metadata_bytes=size,
                      type_ref_rows=counts.get(1,0), method_def_rows=counts.get(6,0))
    except (ValueError, AttributeError, IndexError, struct.error, UnicodeError) as error:
        result['reason'] = str(error) if isinstance(error,ValueError) else type(error).__name__
    return result
