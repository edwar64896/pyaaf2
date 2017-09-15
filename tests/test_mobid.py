from aaf2.mobid import MobID
from uuid import UUID

import unittest

class MobIDTests(unittest.TestCase):
    def test_mob_id(self):
        m = MobID.new()
        m.material = UUID("52c02cd8-6801-4806-986a-b68c0a0cf9d3")
        m_str = "urn:smpte:umid:060a2b34.01010105.01010f00.13000000.52c02cd8.68014806.986ab68c.0a0cf9d3"

        m2 = MobID(str(m))

        assert m == m2
        m2 = MobID(bytes_le=m.bytes_le)
        assert m == m2
        assert m.int == m2.int

        assert m == MobID(m_str)





if __name__ == "__main__":
    import logging
    # logging.basicConfig(level=logging.DEBUG)
    unittest.main()