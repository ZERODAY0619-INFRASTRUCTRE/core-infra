import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('observer', Path(__file__).with_name('observe-tailnet.py'))
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

class EndpointTests(unittest.TestCase):
    def peer(self, **changes):
        return dict({'Online':True,'Active':True,'TailscaleIPs':['100.113.109.93'], 'CurAddr':'8.8.8.8:41641','Relay':'tok'}, **changes)
    def extract(self, peer):
        return observer.public_peers({'BackendState':'Running','Peer':{'p':peer}})
    def test_direct_public_not_derp_region(self):
        self.assertEqual(self.extract(self.peer()), {'100.113.109.93':'8.8.8.8'})
    def test_non_public_or_missing_endpoint(self):
        for address in ['', '192.168.1.2:123', '100.64.0.1:123', '127.0.0.1:123', '224.0.0.1:123', '[::1]:123', '8.8.8.8:0']:
            with self.subTest(address=address): self.assertEqual(self.extract(self.peer(CurAddr=address)),{})
    def test_disconnected_and_relayed(self):
        for changes in [{'Online':False},{'Active':False},{'PeerRelay':'8.8.8.8:123:1'}]:
            self.assertEqual(self.extract(self.peer(**changes)),{})
        self.assertEqual(observer.public_peers({'BackendState':'Stopped','Peer':{'p':self.peer()}}),{})
    def test_ipv6_public_endpoint(self):
        self.assertEqual(self.extract(self.peer(CurAddr='[2001:4860:4860::8888]:41641')),{'100.113.109.93':'2001:4860:4860::8888'})

if __name__ == '__main__': unittest.main()
