from quart import Quart, request, render_template, jsonify, Response, session
from traceback import format_exc
from random import randint
from itertools import chain
from collections import Counter
from main import *


app = Quart(__name__)
app.config['JSON_SORT_KEYS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = "Strict"
app.secret_key = str(randint(0, 100000000))


@app.route("/")
@app.route("/index.html")
async def _root():

    try:
        return await render_template('index.html')
    except Exception as e:
        return Response(format_exc(), 500, content_type="text/plain")


@app.route("/options")
@app.route("/options.html")
async def _menu():

    options = {}

    try:

        directories = await get_directories()
        options.update({'directories': [directory.name for directory in directories]})

        if _ := request.args.get('directory'):
            options.update({'directory': _})
            session.update({'directory': _})
        else:
            options.update({'directory': session.get('directory')})

        resources = []
        if directory_name := options.get('directory'):

            directory = [directory for directory in directories if directory.name == directory_name][0]
            await directory.get_backend_config()
            await directory.get_workspaces()
            options.update({'workspaces': [workspace.name for workspace in directory.workspaces]})

            if _ := request.args.get('workspace'):
                options.update({'workspace': _})
                session.update({'workspace': _})
            else:
                options.update({'workspace': session.get('workspace')})

            if workspace_name := options.get('workspace'):

                if _ := request.args.get('module'):
                    options.update({'module': _})
                    session.update({'module': _})
                else:
                    options.update({'module': session.get('module')})

                if _ := request.args.get('resource_type'):
                    options.update({'resource_type': _})
                    session.update({'resource_type': _})
                else:
                    options.update({'resource_type': session.get('resource_type')})

                resources = await directory.get_resources(workspace_name)

                #print(len(resources), " were returned initially")
                resources = [resource for resource in resources if resource.get('mode') == 'managed']
                #print(len(resources), " were returned after filtering for managed")

                _ = [resource.get('module') for resource in resources]
                options.update({'modules':  [k for k in Counter(_).keys()]})
                if _ := options.get('module'):
                    resources = [resource for resource in resources if resource.get('module') == _ and _ != "ALL"]
                    #print(len(resources), " were returned after filtering for specific module")

                _ = [resource.get('type') for resource in resources]
                options.update({'resource_types': [k for k in Counter(_).keys()]})
                if _ := options.get('resource_type'):
                    resources = [resource for resource in resources if resource.get('type') == _ and _ != "ALL"]
                    #print(len(resources), " were returned after filtering for specific resource type")

                options.update({'index_keys': set([resource['resource'].get('index_key') for resource in resources])})

                #if selected_resource_type := request.args.get('resource'):
                #    session.update({'resource': selected_resource})

        return await render_template(
            template_name_or_list='options.html',
            directories=options.get('directories', []), directory=options.get('directory', ""),
            workspaces=options.get('workspaces', []), workspace=options.get('workspace', ""),
            modules=options.get('modules', []), module=options.get('module', ""),
            resource_types=options.get('resource_types', []), resource_type=options.get('resource_type', ""),
            index_keys=options.get('index_keys', []), num_resources=len(resources)
        )

        #return await render_template('menu.html', directories=directories.keys(), directory=directory, workspaces=workspaces, workspace=workspace)
    except Exception as e:
        return Response(format_exc(), 500, content_type="text/plain")


@app.route("/resources")
@app.route("/resources.html")
async def _resources():

    try:

        resources = []
        if directory_name := request.args.get('directory', session.get('directory')):

            directories = await get_directories()
            directory = [directory for directory in directories if directory.name == directory_name][0]
            await directory.get_backend_config()
            await directory.get_workspaces()

            if workspace_name := request.args.get('workspace', session.get('workspace')):
                resources = await directory.get_resources(workspace_name)    # Get only specific resource
            else:
                resources = await directory.get_resources()   # Get all workspaces
            resources = [resource for resource in resources if resource.get('mode') == 'managed']

            print(len(resources), " were returned initially")
            # Check for module, resource type, and index key filters
            if _ := request.args.get('module', session.get('module')):
                print("modules filter:", _)
                if _ != "":
                    resources = [resource for resource in resources if resource.get('module') == _]
            if _ := request.args.get('resource_type', session.get('resource_type')):
                print("resource_types filter:", _)
                if _ != "":
                    resources = [resource for resource in resources if resource.get('type') == _]
            if _ := request.args.get('index_key', session.get('index_key')):
                if _ != "":
                    resources = [resource for resource in resources if resource.get('index_key') == _]
            print(len(resources), " were returned after filtering")

        resources = [json.dumps(resource, indent=2) for resource in resources]
        return await render_template('resources.html', resources=resources)

    except Exception as e:
        return Response(format_exc(), 500, content_type="text/plain")


if __name__ == '__main__':

    app.run(debug=True)

