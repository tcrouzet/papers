import yaml

def site_yml(path):
    with open(path, 'r') as file:
        return yaml.safe_load(file)
