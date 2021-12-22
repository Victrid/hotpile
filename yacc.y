%{
#include <stdio.h>
#include <string.h>
int yydebug = 1;

%}

%token DEFINE TAPE PSEUDO INSTATE OUTSTATE SEMICOLON MIDPL MIDPR MIDPLNEG LARGEPL LARGEPR COMMA DOLLAR PERCENT SYMBOL

%union {
        char *str;              
    };

%type <str> SYMBOL

%%

enter: { printf("[\n");} def { printf("]\n");};

def: definition
    | definition {printf(",");} def
    ;


definition: DEFINE { printf("{\n");}  SYMBOL { printf("\"name\": \""); printf($3); printf("\",\n");} MIDPL { printf("\"config\": {\n");} config MIDPR { printf("},\n\"code\": [\n");} LARGEPL expr_connect LARGEPR {printf("]}\n");}
        ;

pseu: SYMBOL {printf("\""); printf($1); printf("\"");} 
    | SYMBOL COMMA {printf("\""); printf($1); printf("\",");} pseu
    ;

tpe: SYMBOL {printf("\""); printf($1); printf("\"");} 
    | SYMBOL COMMA {printf("\""); printf($1); printf("\",");} tpe
    ;

item: TAPE { printf("\"tape\": [");} tpe SEMICOLON { printf("]\n");}
    | PSEUDO { printf("\"pseudo\": [");} pseu SEMICOLON { printf("]\n");}
    | INSTATE SYMBOL SEMICOLON {printf("\"in_state\": \""); printf($2); printf("\"\n");} 
    | OUTSTATE {printf("\"out_state\": [");} outstates SEMICOLON { printf("]\n");} 
    ;
    
outstates: {printf("\"");} SYMBOL {printf($2); printf("\"");} outstates_more;

outstates_more: /* empty */
        | COMMA {printf(", \"");} SYMBOL {printf($3); printf("\"");} outstates_more
        ;

config: item
        | item {printf(",\n");} config
        ;

expr_connect: {printf("[");} itemlist {printf("]\n");} exprlist;

exprlist: /* empty */
        | {printf(",[");} itemlist {printf("]\n");} exprlist
        ;

itemlist:  expr SEMICOLON
        | expr COMMA {printf(",\n");} itemlist
        ;

expr: SYMBOL {printf("\"SYMBOL "); printf($1); printf("\"");}
        | DOLLAR LARGEPL SYMBOL LARGEPR {printf("\"PSEUDO "); printf($3); printf("\"");}
        | PERCENT LARGEPL SYMBOL LARGEPR {printf("\"SPECIAL "); printf($3); printf("\"");}
        | MIDPL DOLLAR LARGEPL SYMBOL LARGEPR MIDPR {printf("\"GPSEUDO "); printf($4); printf("\"");}
        | MIDPL PERCENT LARGEPL SYMBOL LARGEPR MIDPR {printf("\"GSPECIAL "); printf($4); printf("\"");}
        | MIDPL SYMBOL MIDPR {printf("\"LIST "); printf($2); printf("\"");}
        | MIDPLNEG DOLLAR LARGEPL SYMBOL LARGEPR MIDPR {printf("\"NPSEUDO "); printf($4); printf("\"");}
        | MIDPLNEG PERCENT LARGEPL SYMBOL LARGEPR MIDPR {printf("\"NSPECIAL "); printf($4); printf("\"");}
        | MIDPLNEG SYMBOL MIDPR {printf("\"NLIST "); printf($2); printf("\"");}
        ;
        
        

%%

int main()
{
    FILE* yyin = stdin;
    yyparse();
    fclose(yyin);
    return 0;
}

int yyerror(char *msg)
{
    printf("Error encountered: %s \n", msg);
}
