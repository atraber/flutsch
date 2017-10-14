#!/usr/bin/env python3
from alexer import Lexer

lexer = Lexer(
    symbols = ('(', ')', '.', ',', '{', '}', "[", "]", ';', ':', '!', '=', '+', '-', '*', '/', '==', '!=', '<=', '>=', '<', '>', '||', '&&'),
    keywords = ('for', 'while', 'if', 'else', 'struct', 'trans', 'on', 'let', 'fsm', 'clk', 'in', 'fork'))


with open("flutsch.flutsch") as f:
    content = f.read()

tokens = lexer.lex(content)

for token in tokens:
    if token.type == 'NEWLINE' or token.type == 'INDENT' or token.type == 'DEDENT':
        continue
    if token.type == 'SYMBOL':
        if token.value == '.':
            token.type = 'DOT'
        elif token.value == ',':
            token.type = 'COMMA'
        elif token.value == ';':
            token.type = 'SEMICOLON'
        elif token.value == ':':
            token.type = 'COLON'
        elif token.value == '(':
            token.type = 'LPAR'
        elif token.value == ')':
            token.type = 'RPAR'
        elif token.value == '{':
            token.type = 'LBRACE'
        elif token.value == '}':
            token.type = 'RBRACE'
        elif token.value == '!':
            token.type = 'NOT'
        elif token.value == '==':
            token.type = 'EQ'
        elif token.value == '!=':
            token.type = 'NEQ'
        elif token.value == '<=':
            token.type = 'LEQ'
        elif token.value == '>=':
            token.type = 'GEQ'
        elif token.value == '<':
            token.type = 'LT'
        elif token.value == '>':
            token.type = 'GT'
        elif token.value == '=':
            token.type = 'ASSIGN'
        elif token.value == '+':
            token.type = 'ADD'
        elif token.value == '-':
            token.type = 'SUB'
        elif token.value == '*':
            token.type = 'MUL'
        elif token.value == '/':
            token.type = 'DIV'
        elif token.value == '||':
            token.type = 'LOR'
        elif token.value == '&&':
            token.type = 'LAND'
    elif token.type == 'NAME':
        token.type = 'IDENT'
    elif token.type == 'INT':
        token.type = 'NUM_LIT'
    elif token.type == 'END':
        token.type = 'EOF'

    print('%10s%15s%10s' % (token.type, token.value, token.location))
