import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sync_pipeline_data


class PipelineDataSyncTest(unittest.TestCase):
    @mock.patch.object(sync_pipeline_data, "ref_exists", return_value=True)
    def test_no_push_prefers_existing_local_data_branch(self, ref_exists):
        self.assertEqual(
            sync_pipeline_data.resolve_publish_ref("origin", push=False),
            "refs/heads/data",
        )
        ref_exists.assert_called_once_with("refs/heads/data")

    @mock.patch.object(sync_pipeline_data, "resolve_data_ref", return_value="refs/remotes/origin/data")
    def test_push_uses_remote_data_branch_as_base(self, resolve_data_ref):
        self.assertEqual(
            sync_pipeline_data.resolve_publish_ref("origin", push=True),
            "refs/remotes/origin/data",
        )
        resolve_data_ref.assert_called_once_with("origin")


if __name__ == "__main__":
    unittest.main()
