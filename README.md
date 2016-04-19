sspam: Symbolic Simplification with PAttern Matching
====================================================

For some sort of roadmap with developpement ideas:
[SSPAM libreboard (internal QB)](http://libreboard.dmz.qb/b/w5JbCyxXdciWN8rGQ/sspam)


Requirements
------------
To use sspam, you need:

* The SMT solver [z3](https://github.com/Z3Prover/z3)
* The Python library for symbolic mathematics [sympy](http://www.sympy.org/fr/index.html)
* The Python module for ast unparsing [astunparse](https://github.com/simonpercivall/astunparse)


Installation
------------

* You can install sympy and astunparse with `pip install -r requirements.txt`

* To install z3, you can either:
 * Compile it from [source](https://github.com/Z3Prover/z3)
 * Or download a [release](https://github.com/Z3Prover/z3/releases) and
  add the `bin/` directory to your `$PYTHONPATH`

* To install SSPAM:

```
$ cd sspam_directory
$ sudo python setup.py install
```

Using sspam
------------

You can use sspam either with the command line:

```
$ sspam "(x & y) + (x | y)"

(x + y)

```

Or in a python script:

```
from sspam import simplifier

print simplifier.simplify("(x & y) + (x | y)")
```

You'll see a few examples of utilisation of sspam in the examples/
directory.

Know that expressions passed to the simplifier should be in
cse form (a list of assignment), as provided by the cse module.


Tests
-----

To run tests of sspam:

```
$ cd tests/
$ python run_all_tests.py
```
