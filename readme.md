# Hotpile: High Order Turing Machine Language Compiler

## Build and Run

**Requirements**: Python 3.6+, bison, flex, and GCC installed. Needs to be run under UNIX like OS. Only Linux is tested. 

To build: run `./compile.sh` to compile the parser.

**Run**: With the example script under Universal Turing Machine:

```
python ./hotpile.py "Universal Turing Machine/main.tb" > out.turing
```

The code is out and can be copy-pasted into [Turing Machine Simulator](https://turingmachinesimulator.com/).
