import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.normpath(os.path.join(script_dir, '..', '..', '..'))

configlines = open(os.path.join(project_root, 'config', 'private_client.prc'), 'r').read()
data = 'CONFIGFILE = %s\n' % configlines.encode('utf-8')

dclines = open(os.path.join(project_root, 'config', 'ttph.dc'), 'r').read()
data += 'DCFILE = %s\n' % dclines.encode('utf-8')

out = os.path.join(project_root, 'PrivacyMatters.py')
open(out, 'w').write(data)
print('Wrote %s' % out)