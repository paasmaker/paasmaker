
from distutils.core import setup

try:
  import setuptools
except ImportError:
  pass

setup(
  name='safeclose',
  version='0.1.0',
  description='An easy way to ensure that programs will exit in safe fashion',
  author='Andrei Savu',
  author_email='savu.andrei@gmail.com',
  url='http://github.com/andreisavu/safeclose',
  py_modules=['safeclose'],
  classifiers=[
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Programming Language :: Python',
    'License :: OSI Approved :: Apache Software License',
    'Operating System :: Unix',
  ],
)

