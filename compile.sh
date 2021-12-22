#!/bin/bash
lex lex.l
yacc -d -Wcounterexamples yacc.y
gcc -c lex.yy.c
gcc -c y.tab.c
gcc lex.yy.o y.tab.o -o parser
rm y.tab* lex.yy*
