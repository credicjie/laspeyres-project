import json, oss2
from pathlib import Path

class OSSClient:
    def __init__(self, config_path):
        self.config_path = Path(config_path)
        self._bucket = None

    def _load_config(self):
        with open(self.config_path, encoding='utf-8') as f:
            return json.load(f)['oss']

    def _get_bucket(self):
        if self._bucket is not None:
            return self._bucket
        cfg = self._load_config()
        auth = oss2.Auth(cfg['access_key_id'], cfg['access_key_secret'])
        self._bucket = oss2.Bucket(auth, cfg['endpoint'], cfg['bucket_name'])
        return self._bucket

    def is_configured(self):
        try:
            cfg = self._load_config()
            return all([cfg.get(k) for k in ['access_key_id', 'access_key_secret', 'endpoint', 'bucket_name']])
        except:
            return False

    def upload_file(self, local_path, oss_key):
        if not self.is_configured():
            return False
        bucket = self._get_bucket()
        try:
            bucket.put_object_from_file(oss_key, local_path)
            print(f"  -> 已上传: {oss_key}")
            return True
        except oss2.exceptions.OssError as e:
            print(f"  x 上传失败 {oss_key}: {e}")
            return False

    def read_raw(self, oss_key):
        """读取 OSS 文件内容为字符串"""
        try:
            bucket = self._get_bucket()
            result = bucket.get_object(oss_key)
            return result.read().decode('utf-8', errors='replace')
        except oss2.exceptions.OssError as e:
            print(f"  x 读取失败 {oss_key}: {e}")
            return None

    def read_csv_sample(self, oss_key, nrows=5):
        """读取 OSS 中 CSV 的前 nrows 行，返回 DataFrame"""
        import pandas as pd
        raw = self.read_raw(oss_key)
        if raw is None:
            return None
        import io
        try:
            return pd.read_csv(io.StringIO(raw), nrows=nrows, encoding='gbk')
        except:
            return pd.read_csv(io.StringIO(raw), nrows=nrows, encoding='utf-8')

    def get_bucket_name(self):
        return self._load_config().get('bucket_name', 'unknown')
