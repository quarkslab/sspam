This is sspam: Symbolic Simplification with PAttern Matching.

For some sort of roadmap:
http://libreboard.dmz.qb/b/w5JbCyxXdciWN8rGQ/sspam


Requirements
-------------

To use sspam, you need:

 * z3
   - Compile it from https://github.com/Z3Prover/z3
   - Or download a release from
     https://github.com/Z3Prover/z3/releases and add the bin/
     directory to your PYTHONPATH

 * sympy: install it with `pip install sympy`



Using sspam
------------

You'll see a few examples of utilisation of sspam in the examples/
directory. Know that expressions passed to the simplifier should be in
cse form (a list of assignment), as provided by the cse module.
