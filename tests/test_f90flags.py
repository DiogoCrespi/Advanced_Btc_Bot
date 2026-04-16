import re
from unittest.mock import patch, mock_open

# Mock split_quoted to test standalone
def split_quoted(s):
    return s.split()

_f90flags_re = re.compile(r'(c|!|)f90flags\s*\(\s*(?P<fcname>\w+)\s*\)\s*=\s*(?P<fflags>.*)', re.I)
def get_f90flags(src):
    flags = {}
    with open(src, encoding='latin1') as f:
        i = 0
        for line in f:
            i += 1
            if i>20: break
            m = _f90flags_re.match(line)
            if not m: continue
            fcname = m.group('fcname').strip()
            fflags = m.group('fflags').strip()
            flags[fcname] = split_quoted(fflags)
    return flags

def test_get_f90flags():
    mock_src = "!F90FLAGS(gfortran) = -O3 -march=native\n! Other comment\ncF90FLAGS(intel)=-O2\nf90flags(pgi) = -fast\n"
    with patch("builtins.open", mock_open(read_data=mock_src)):
        flags = get_f90flags("dummy.f90")
        assert flags == {
            "gfortran": ["-O3", "-march=native"],
            "intel": ["-O2"],
            "pgi": ["-fast"]
        }
    print("Test passed!")

if __name__ == "__main__":
    test_get_f90flags()
