import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

class DeliveryTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('research_projects.ood_augmentation.delivery'))
        from research_projects.ood_augmentation import delivery
        return delivery

    def test_pages_preserve_source_rows_and_exclude_private_files(self):
        m=self.module()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);public=root/'public';public.mkdir()
            rows=[{'sample_id':str(i),'x':[1,1,1],'y':[.5]*118} for i in range(20)]
            files={}
            for name in ('train','id_dev','diagnostic'):
                path=public/(name+'.json');path.write_text(json.dumps(rows));files[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
            (public/'manifest.json').write_text(json.dumps({'files':files}))
            (public/'private.json').write_text('SECRET')
            result=m.prepare_views(public,root/'views')
            for split in ('train','id_dev','diagnostic'):
                recovered=[]
                for page in result['splits'][split]['pages']:
                    body=(root/'views'/page['file']).read_bytes()
                    self.assertLessEqual(len(body),40000)
                    recovered.extend(json.loads(line) for line in body.splitlines())
                self.assertEqual(recovered,rows)
            self.assertFalse((root/'views/private.json').exists())
            (public/'train.json').write_text('[]')
            with self.assertRaises(ValueError):m.prepare_views(public,root/'other')
