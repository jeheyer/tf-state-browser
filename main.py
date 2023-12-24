#!/usr/bin/env python3

from asyncio import run, gather
from gcloud.aio.auth import Token
from gcloud.aio.storage import Storage
from google.oauth2.service_account import Credentials
from subprocess import Popen, PIPE
from platform import system
from os import environ, scandir
import google.auth
import google.auth.transport.requests
import json

#TF_BASE = '/mnt/homes/j5/OpenText/repos/otc-network/terraform/'
#TF_BASE = '../../../../OneDrive - OpenText/repos/otc-network/terraform/'
TF_BASE = '../otc-network/terraform/'
DIRECTORIES = ['root', 'vm-services', 'network-services', 'vpc-network', 'gcp_vpc_network', 'hybrid-networking', 'lb']
SCOPES = ["https://www.googleapis.com/auth/cloud-platform.read-only"]
REQUEST_TIMEOUT = 3


class Bucket:

    def __init__(self, bucket_type: str, name: str):

        self.type = bucket_type.lower()
        self.name = name
        self.token = None
        if self.type == "gcs":

            if adc_file := environ.get('GOOGLE_APPLICATION_CREDENTIALS'):
                credentials = Credentials.from_service_account_file(adc_file, scopes=SCOPES)
                credentials.refresh(google.auth.transport.requests.Request())
                self.token = credentials.token
                print("ADC Token is:", self.token)
            elif 1 == 2:
                # Regular ADC
                credentials, project_id = google.auth.default(scopes=SCOPES, quota_project_id=None)
            else:
                self.token = Token(scopes=SCOPES)


class WorkSpace:

    def __init__(self, name: str = 'default', state_file: str = 'default.tfstate'):

        self.name = name
        self.state_file = state_file


class BackendConfig:

    def __init__(self, backend_type: str = 'local'):

        self.type = backend_type
        self.bucket = None
        self.bucket_prefix = None

    def set_bucket(self, bucket_name: str, bucket_prefix: str = ""):

        self.bucket = Bucket(self.type, bucket_name)
        self.bucket_prefix = bucket_prefix


class Directory:

    def __init__(self, base_dir: str = '/'):

        self.os = system().lower()
        self.base_dir = base_dir.replace("/", "\\") if self.os.startswith("win") else base_dir
        self.name = self.base_dir.split('\\')[-1] if self.os.startswith('win') else self.base_dir.split('/')[-1]
        self.backend_config = BackendConfig()
        self.workspaces = []

    async def get_backend_config(self):

        # Examine .tf files in this directory for a backend configuration
        tf_files = [f.name for f in scandir(self.base_dir) if f.name.lower().endswith(".tf")]
        for tf_file in tf_files:
            with open(f"{self.base_dir}/{tf_file}", 'r') as fp:
                for line in fp:
                    if 'terraform ' in line:
                        line = next(fp)
                        if 'backend ' in line:
                            self.backend_config.type = line.split("\"")[1].lower()
                            in_backend = True
                            while in_backend:
                                if self.backend_config.type in ['s3', 'gcs']:
                                    line = next(fp)
                                    if '}' in line:
                                        in_backend = False
                                    else:
                                        if 'bucket ' in line:
                                            bucket_name = line.split("\"")[1]
                                            self.backend_config.set_bucket(bucket_name)
                                        if 'prefix ' in line:
                                            bucket_prefix = line.split("\"")[1]
                                            self.backend_config.bucket_prefix = bucket_prefix
                            break

                    else:
                        continue
                #if self.backend_config.backend_type in ['s3', 'gcs']:
                #s    self.bucket = Bucket(type=self.backend_type, name=self.bucket_name)

    async def get_workspaces(self):

        #print("bucket info:", self.bucket.__dict__)
        if self.backend_config.type == 'gcs':

            bucket_name = self.backend_config.bucket.name
            bucket_prefix = self.backend_config.bucket_prefix
            print("Getting workspaces for", self.backend_config.type, bucket_name, bucket_prefix)

            params = {'prefix': bucket_prefix}
            token = self.backend_config.bucket.token
            async with Storage(token=token) as storage:
                while True:
                    response = await storage.list_objects(bucket_name, params=params, timeout=REQUEST_TIMEOUT)
                    for obj in response.get('items', []):
                        if obj['name'].lower().endswith('.tfstate') and int(obj.get('size', 0)) > 0:
                            state_file = obj['name']
                            _ = state_file.replace(".tfstate", "")
                            workspace_name = _.replace(f"{bucket_prefix}/", "")
                            print("found state file:", state_file)
                            workspace = WorkSpace(workspace_name, state_file)
                            self.workspaces.append(workspace)
                    if page_token := response.get('nextPageToken'):
                        params.update({'pageToken':  page_token})
                    else:
                        break
                await token.close()

    async def get_resources(self, workspace_name: str = None) -> list:

        resources = []

        if workspace_name:
            workspaces = [workspace for workspace in self.workspaces if workspace.name == workspace_name]
        else:
            workspaces = self.workspaces
        print(len(workspaces), "were fetched in directory", self.name)
        for workspace in workspaces:
            if self.backend_config.type == 'gcs':
                token = self.backend_config.bucket.token
                async with Storage(token=token) as storage:
                    state_file = workspace.state_file
                    print("fetching", state_file, "from bucket", self.backend_config.bucket.name)
                    blob = await storage.download(self.backend_config.bucket.name, state_file, timeout=REQUEST_TIMEOUT)
                await token.close()

            _ = json.loads(blob.decode())
            for resource in _.get('resources', []):
                for instance in resource.get('instances', []):
                    resources.append({
                        'name': resource.get('name'),
                        'type': resource.get('type'),
                        'module': resource.get('module'),
                        'mode': resource.get('mode'),
                        'resource': instance,
                    })

        return resources

            #return ["aklsjdf", "laksjdf", "alskdfjlasdkfjdlsakfjalsdkf"]


def run_command(command: str, directory: str = "./") -> list:

    try:
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True, cwd=directory)
        stdout = process.stdout.read()
        stderr = process.stderr.read()
    except Exception as e:
        raise RuntimeError(e)

    return [line.strip() for line in stdout.decode("utf-8").splitlines()]


async def get_directories(directory_names: list = None) -> dict:

    try:
        if not directory_names:
            #directory_names = DIRECTORIES
            directory_names = [d.name for d in scandir(TF_BASE) if d.is_dir()]
        _ = [Directory(f"{TF_BASE}{directory_name}") for directory_name in directory_names]
        return _
    except Exception as e:
        raise e


async def main():

    directories = await get_directories()

    try:
        tasks = [directory.get_backend_config() for directory in directories]
        [_ for _ in await gather(*tasks)]

        tasks = [directory.get_workspaces() for directory in directories]
        [_ for _ in await gather(*tasks)]
    except Exception as e:
        quit(e)
    #print(directories)
    for directory in directories:
        #backend_config = await get_backend_config(module)
        print(directory.name, directory.backend_config.type, directory.backend_config.bucket.name, directory.backend_config.bucket_prefix, len(directory.workspaces))
    #_ = await get_data('dns', "laksjd")
    #print(_)


if __name__ == '__main__':

    run(main())
