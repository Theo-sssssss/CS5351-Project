# Webhook 签名测试：验证正确签名被接受，伪造或错误签名被拒绝。

import hashlib
import hmac
import unittest

from evoagent.github import verify_signature


# 集中验证本模块的正常行为、错误路径及数据边界。
class GitHubSignatureTests(unittest.TestCase):
    # 验证合法 HMAC 签名被接受，错误签名被拒绝。
    def test_signature_verification(self):
        body = b'{"ok":true}'
        signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_signature("secret", body, signature))
        self.assertFalse(verify_signature("wrong", body, signature))


if __name__ == "__main__":
    unittest.main()

