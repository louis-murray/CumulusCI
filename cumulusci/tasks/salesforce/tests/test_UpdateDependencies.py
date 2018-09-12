import io
import mock
import unittest
import zipfile

from cumulusci.core.config import OrgConfig
from cumulusci.core.exceptions import TaskOptionsError
from cumulusci.tasks.salesforce import UpdateDependencies
from cumulusci.tests.util import create_project_config
from .util import create_task


class TestUpdateDependencies(unittest.TestCase):
    @mock.patch(
        "cumulusci.salesforce_api.metadata.ApiRetrieveInstalledPackages.__call__"
    )
    def test_run_task(self, ApiRetrieveInstalledPackages):
        project_config = create_project_config()
        project_config.config["project"]["dependencies"] = [
            {
                "zip_url": "http://zipurl",
                "subfolder": "src",
                "namespace_tokenize": "ns",
                "namespace_inject": "ns",
                "namespace_strip": "ns",
                "dependencies": [
                    {"namespace": "upgradeddep", "version": "1.1"},
                    {"namespace": "samedep", "version": "1.0"},
                    {"namespace": "downgradeddep", "version": "1.0"},
                    {"namespace": "newdep", "version": "1.0"},
                ],
            },
            {
                "namespace": "dependsonupgradedbeta",
                "version": "1.0",
                "dependencies": [
                    {"namespace": "upgradedbeta", "version": "1.0 (Beta 2)"}
                ],
            },
        ]
        task = create_task(UpdateDependencies, project_config=project_config)
        ApiRetrieveInstalledPackages.return_value = {
            "upgradeddep": "1.0",
            "samedep": "1.0",
            "downgradeddep": "1.1",
            "removeddep": "1.0",
            "upgradedbeta": "1.0 (Beta 1)",
            "dependsonupgradedbeta": "1.0",
        }
        task.api_class = mock.Mock()
        zf = zipfile.ZipFile(io.BytesIO(), "w")
        with mock.patch.dict(
            "cumulusci.tasks.salesforce.UpdateDependencies._install_dependency.__func__.__globals__",
            download_extract_zip=mock.Mock(return_value=zf),
        ):
            task()
        self.assertEqual(
            [
                {"version": "1.1", "namespace": "upgradeddep"},
                {"version": "1.0", "namespace": "downgradeddep"},
                {"version": "1.0", "namespace": "newdep"},
                {
                    "dependencies": [
                        {"version": "1.1", "namespace": "upgradeddep"},
                        {"version": "1.0", "namespace": "samedep"},
                        {"version": "1.0", "namespace": "downgradeddep"},
                        {"version": "1.0", "namespace": "newdep"},
                    ],
                    "zip_url": "http://zipurl",
                    "subfolder": "src",
                    "namespace_tokenize": "ns",
                    "namespace_inject": "ns",
                    "namespace_strip": "ns",
                },
                {"version": "1.0 (Beta 2)", "namespace": "upgradedbeta"},
                {
                    "version": "1.0",
                    "namespace": "dependsonupgradedbeta",
                    "dependencies": [
                        {"version": "1.0 (Beta 2)", "namespace": "upgradedbeta"}
                    ],
                },
            ],
            task.install_queue,
        )
        self.assertEqual(
            [
                {
                    "version": "1.0",
                    "namespace": "dependsonupgradedbeta",
                    "dependencies": [
                        {"version": "1.0 (Beta 2)", "namespace": "upgradedbeta"}
                    ],
                },
                {"version": "1.0 (Beta 2)", "namespace": "upgradedbeta"},
                {"version": "1.0", "namespace": "downgradeddep"},
            ],
            task.uninstall_queue,
        )
        self.assertEqual(9, task.api_class.call_count)

    def test_run_task__no_dependencies(self):
        task = create_task(UpdateDependencies)
        api = mock.Mock()
        task.api_class = mock.Mock(return_value=api)
        task()
        api.assert_not_called()

    def test_update_dependency_latest_option_err(self):
        project_config = create_project_config()
        project_config.config["project"]["dependencies"] = [{"namespace": "foo"}]
        task = create_task(UpdateDependencies, project_config=project_config)
        task.options["install_latest"] = True
        task.org_config = OrgConfig(None, None)

        with self.assertRaises(TaskOptionsError):
            task()
