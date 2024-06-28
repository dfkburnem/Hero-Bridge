from setuptools import setup, find_packages

setup(
    name='hero_bridge',
    version='1.0.0',  
    packages=find_packages(),  
    py_modules=['hero_bridge'],
    install_requires=[
        'cryptography>=40.0.2',
        'web3>=6.4.0',
    ],
    entry_points={
        'console_scripts': [
            'hero_bridge=hero_bridge:main',
        ],
    },
    author='burnem',  
    author_email='dfkburnem@gmail.com',  
    description='A GUI for automating bridging heroes in DFK',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/dfkburnem/Hero-Bridge',  
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Microsoft :: Windows',
    ],
    python_requires='>=3.6,<4',
)
