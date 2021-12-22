%{
#include "y.tab.h"
#include <stdio.h>
#include <string.h>
%}

ident_char [A-Za-z<>#:0-9_-]
SYMBOL {ident_char}+
blank ([ \f\r\t\v]+)

%%


define {return DEFINE;}
tape {return TAPE;}
pseudo {return PSEUDO;}
in_state {return INSTATE;}
out_state {return OUTSTATE;}
";" {return SEMICOLON;}
"]" {return MIDPR;}
"[^" {return MIDPLNEG;}
"[" {return MIDPL;}
"{" {return LARGEPL;}
"}" {return LARGEPR;}
"," {return COMMA;}
"$" {return DOLLAR;}
"%" {return PERCENT;}
{blank} {}
{SYMBOL} {yylval.str=strdup(yytext); return SYMBOL;}

%%

int yywrap(void)
{
    return 1;
}
