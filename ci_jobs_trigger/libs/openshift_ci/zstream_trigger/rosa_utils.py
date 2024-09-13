import re
from typing import Dict, List

import rosa.cli
from ocm_python_wrapper.ocm_client import OCMPythonClient


# Move to rosa library
def get_rosa_versions(ocm_client: OCMPythonClient, aws_region: str, channel_group: str, hosted_cp: bool = False):
    rosa_base_available_versions_dict: Dict[str, Dict[str, List[str]]] = {}
    base_available_versions = rosa.cli.execute(
        command=(f"list versions --channel-group={channel_group} " f"{'--hosted-cp' if hosted_cp else ''}"),
        aws_region=aws_region,
        ocm_client=ocm_client,
    )["out"]
    _all_versions = [ver["raw_id"] for ver in base_available_versions]
    rosa_base_available_versions_dict[channel_group] = {}
    for _version in _all_versions:
        _version_key = re.findall(r"^\d+.\d+", _version)[0]
        rosa_base_available_versions_dict[channel_group].setdefault(_version_key, []).append(_version)

    return rosa_base_available_versions_dict
