# An experimental parser for the Flutsch language.
import sys
import re
import yaml
import pickle

PREC_MAX     = 99
PREC_LOR     = 8
PREC_LAND    = 7
PREC_REL     = 6
PREC_ADD     = 5
PREC_MUL     = 4
PREC_UNARY   = 3
PREC_MEM     = 2
PREC_PRIMARY = 1

class Parser(object):
	def __init__(self, lexer):
		super(Parser, self).__init__()
		self.lexer = lexer
		self.next = self.lexer.pop()

	def bump(self):
		self.next = self.lexer.pop()

	def error(self, msg):
		sys.stderr.write("error: ")
		sys.stderr.write(msg)
		sys.stderr.write("\n")
		sys.exit(1)

	# Check if the next token matches and consume it, otherwise return False.
	def accept(self, tkn):
		if self.next.type == tkn:
			self.bump()
			return True
		else:
			return False

	def require(self, tkn):
		t = self.next
		if not self.accept(tkn):
			self.error("expected `%s`, found `%s` instead" % (tkn, self.next.value))
		return t

	# Apply the parser `fn` multiple times until the token `end` is encountered.
	def repeat_until(self, fn, end):
		l = list()
		while self.next.type != end:
			if self.next.type == "EOF":
				self.error("unexpected end of file")
			l.append(fn())
		return l

	# Apply the parser `fn` multiple times, separated by `sep`, until the token
	# `end` is encountered.
	def separated(self, fn, sep, end):
		l = list()
		while self.next.type != end:
			if self.next.type == "EOF":
				self.error("unexpected end of file")
			l.append(fn())
			if self.next.type == sep:
				self.bump()
				if self.next.type == end:
					break
			elif self.next.type != end:
				self.error("expected %s" % sep)
		return l


	def parse(self):
		units = self.repeat_until(self.parse_unit, "EOF")
		print(yaml.dump(units, indent=2))
		return units

	def parse_ident(self):
		if self.next.type == "IDENT":
			n = self.next.value
			self.bump()
			return n
		else:
			self.error("expected identifier")

	def parse_unit(self):
		if self.accept("KW_STRUCT"):
			name = self.parse_ident()
			self.require("LBRACE")
			fields = self.separated(self.parse_struct_field, "SEMICOLON", "RBRACE")
			self.require("RBRACE")
			return Struct(name, fields)

		elif self.accept("KW_FSM"):
			name = self.parse_ident()
			self.require("LBRACE")
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return Fsm(name, stmts)

		elif self.accept("KW_TRANS"):
			name = self.parse_ident()
			self.require("LPAR")
			args = self.separated(self.parse_arg, "COMMA", "RPAR")
			self.require("RPAR")
			self.require("KW_ON")
			on = self.parse_ident()
			self.require("LBRACE")
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return Trans(name, args, on, stmts)

		else:
			self.error("expected struct, fsm, or trans")

	def parse_struct_field(self):
		name = self.parse_ident()
		self.require("COLON")
		rev = self.accept("NOT")
		ty = self.parse_type()
		return StructField(name, rev, ty)

	def parse_type(self):
		if self.accept("LBRACK"):
			ty = self.parse_type()
			self.require("RBRACK")
			return ArrayTy(ty)
		else:
			name = self.parse_ident()
			m = re.match('int([0-9]+)', name)
			if m:
				return IntTy(int(m.group(1)))
			else:
				return NamedTy(name)

	def parse_arg(self):
		name = self.parse_ident()
		self.require("COLON")
		ty = self.parse_type()
		return Arg(name, ty)

	def parse_stmt_SHOUT(self):
		s = self.parse_stmt();
		print("STMT: \033[31;1m%s\033[m" % s)
		return s

	def parse_stmt(self):
		if self.accept("SEMICOLON"):
			return None

		elif self.accept("LBRACE"):
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return BlockStmt(stmts)

		elif self.accept("KW_CLK"):
			self.require("SEMICOLON")
			return ClkStmt()

		elif self.accept("KW_WHILE"):
			cond = self.parse_expr()
			self.require("LBRACE")
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return WhileStmt(cond, stmts)

		elif self.accept("KW_FOR"):
			var = self.parse_ident()
			self.require("KW_IN")
			rng = self.parse_expr()
			self.require("LBRACE")
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return ForStmt(var, rng, stmts)

		elif self.accept("KW_FORK"):
			self.require("LBRACE")
			stmts = self.repeat_until(self.parse_stmt_SHOUT, "RBRACE")
			self.require("RBRACE")
			return ForkStmt(stmts)

		elif self.accept("KW_LET"):
			name = self.parse_ident()
			if self.accept("COLON"):
				ty = self.parse_type()
			else:
				ty = None
			self.require("SEMICOLON")
			return LetStmt(name, ty)

		else:
			expr = self.parse_expr()
			if self.accept("ASSIGN"):
				rhs = self.parse_expr()
				self.require("SEMICOLON")
				return AssignStmt(expr, rhs)
			else:
				self.require("SEMICOLON")
				return ExprStmt(expr)

	def parse_expr(self):
		return self.parse_expr_prec(PREC_MAX)

	def parse_expr_prec(self, prec):
		expr = None

		# Handle unary expressions.
		if prec >= PREC_UNARY:
			if self.accept("ADD"):
				arg = self.parse_expr_prec(PREC_UNARY)
				expr = UnaryExpr("ADD", arg)
			elif self.accept("SUB"):
				arg = self.parse_expr_prec(PREC_UNARY)
				expr = UnaryExpr("SUB", arg)
			elif self.accept("NOT"):
				arg = self.parse_expr_prec(PREC_UNARY)
				expr = UnaryExpr("NOT", arg)

		# Handle primary expressions.
		if expr is None:
			if self.next.type == "IDENT":
				name = self.next.value
				self.bump()
				expr = IdentExpr(name)
			elif self.next.type == "NUM_LIT":
				value = int(self.next.value)
				self.bump()
				expr = NumLitExpr(value)
			elif self.accept("LPAR"):
				expr = self.parse_expr()
				self.require("RPAR")

		# We need an expression by now.
		if expr is None:
			self.error("expected an expression")

		return self.parse_expr_suffix(expr, prec)

	def parse_expr_suffix(self, prefix, prec):
		print("suffix for %s, prec %s" % (prefix, prec))
		if prec >= PREC_MEM and self.accept("DOT"):
			name = self.parse_ident()
			return self.parse_expr_suffix(MemberExpr(prefix, name), prec)

		elif prec >= PREC_ADD and self.accept("ADD"):
			rhs = self.parse_expr_prec(PREC_ADD)
			return self.parse_expr_suffix(BinaryExpr("ADD", prefix, rhs), prec)
		elif prec >= PREC_ADD and self.accept("SUB"):
			rhs = self.parse_expr_prec(PREC_ADD)
			return self.parse_expr_suffix(BinaryExpr("SUB", prefix, rhs), prec)

		elif prec >= PREC_MUL and self.accept("MUL"):
			rhs = self.parse_expr_prec(PREC_MUL)
			return self.parse_expr_suffix(BinaryExpr("MUL", prefix, rhs), prec)
		elif prec >= PREC_MUL and self.accept("DIV"):
			rhs = self.parse_expr_prec(PREC_MUL)
			return self.parse_expr_suffix(BinaryExpr("DIV", prefix, rhs), prec)

		elif prec >= PREC_REL and self.accept("EQ"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("EQ", prefix, rhs), prec)
		elif prec >= PREC_REL and self.accept("NEQ"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("NEQ", prefix, rhs), prec)
		elif prec >= PREC_REL and self.accept("LT"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("LT", prefix, rhs), prec)
		elif prec >= PREC_REL and self.accept("GT"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("GT", prefix, rhs), prec)
		elif prec >= PREC_REL and self.accept("LEQ"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("LEQ", prefix, rhs), prec)
		elif prec >= PREC_REL and self.accept("GEQ"):
			rhs = self.parse_expr_prec(PREC_REL)
			return self.parse_expr_suffix(BinaryExpr("GEQ", prefix, rhs), prec)

		elif prec >= PREC_LAND and self.accept("LAND"):
			rhs = self.parse_expr_prec(PREC_LAND)
			return self.parse_expr_suffix(BinaryExpr("LAND", prefix, rhs), prec)
		elif prec >= PREC_LOR and self.accept("LOR"):
			rhs = self.parse_expr_prec(PREC_LOR)
			return self.parse_expr_suffix(BinaryExpr("LOR", prefix, rhs), prec)

		elif prec >= PREC_UNARY and self.accept("LPAR"):
			args = self.separated(self.parse_expr, "COMMA", "RPAR")
			self.require("RPAR")
			return CallExpr(prefix, args)

		else:
			return prefix


class Struct:
	def __init__(self, name, fields):
		self.name = name
		self.fields = fields
	def __str__(self):
		return "struct %s {\n%s}" % (self.name, ";\n".join(["%s" % a for a in self.fields]))

class StructField:
	def __init__(self, name, rev, ty):
		self.name = name
		self.rev = rev
		self.ty = ty
	def __str__(self):
		return "%s: %s%s" % (self.name, "! " if self.rev else "", self.ty)

class Fsm:
	def __init__(self, name, stmts):
		self.name = name
		self.stmts = stmts
	def __str__(self):
		return "fsm %s {\n%s }" % (self.name, "\n".join(["%s" % a for a in self.stmts]))

class Trans:
	def __init__(self, name, args, on, stmts):
		self.name = name
		self.args = args
		self.on = on
		self.stmts = stmts
	def __str__(self):
		return "trans %s(%s) on %s {\n%s}" % (self.name, ", ".join(["%s" % a for a in self.args]), self.on, "\n".join(["%s" % a for a in self.stmts]))

class Arg:
	def __init__(self, name, ty):
		self.name = name
		self.ty = ty
	def __str__(self):
		return "%s: %s" % (self.name, self.ty)


class IntTy:
	def __init__(self, width):
		self.width = width
	def __str__(self):
		return "int%d" % self.width

class NamedTy:
	def __init__(self, name):
		self.name = name
	def __str__(self):
		return self.name

class ArrayTy:
	def __init__(self, ty):
		self.ty = ty
	def __str__(self):
		return "[%s]" % self.ty


class ClkStmt:
	def __str__(self):
		return "clk;"

class ExprStmt:
	def __init__(self, expr):
		self.expr = expr
	def __str__(self):
		return "%s;" % self.expr

class AssignStmt:
	def __init__(self, lhs, rhs):
		self.lhs = lhs
		self.rhs = rhs
	def __str__(self):
		return "%s = %s;" % (self.lhs, self.rhs)

class WhileStmt:
	def __init__(self, cond, stmts):
		self.cond = cond
		self.stmts = stmts
	def __str__(self):
		return "while %s {\n%s}" % (self.cond, "\n".join(["%s" % a for a in self.stmts]))

class ForStmt:
	def __init__(self, var, rng, stmts):
		self.var = var
		self.rng = rng
		self.stmts = stmts
	def __str__(self):
		return "for %s in %s {\n%s}" % (self.var, self.rng, "\n".join(["%s" % a for a in self.stmts]))

class BlockStmt:
	def __init__(self, stmts):
		self.stmts = stmts
	def __str__(self):
		return "{\n%s}" % ("\n".join(["%s" % a for a in self.stmts]))

class ForkStmt:
	def __init__(self, stmts):
		self.stmts = stmts
	def __str__(self):
		return "fork {\n%s}" % ("\n".join(["%s" % a for a in self.stmts]))

class LetStmt:
	def __init__(self, name, ty):
		self.name = name
		self.ty = ty
	def __str__(self):
		s = "let %s" % self.name
		if self.ty is not None:
			s += " : %s" % self.ty
		s += ";"
		return s


class IdentExpr:
	def __init__(self, name):
		self.name = name
	def __str__(self):
		return "%s" % self.name

class NumLitExpr:
	def __init__(self, value):
		self.value = value
	def __str__(self):
		return "%s" % self.value

class MemberExpr:
	def __init__(self, expr, name):
		self.expr = expr
		self.name = name
	def __str__(self):
		return "%s.%s" % (self.expr, self.name)

class UnaryExpr:
	def __init__(self, op, arg):
		self.op = op
		self.arg = arg
	def __str__(self):
		return "(%s %s)" % (self.op, self.arg)

class BinaryExpr:
	def __init__(self, op, lhs, rhs):
		self.op = op
		self.lhs = lhs
		self.rhs = rhs
	def __str__(self):
		return "(%s %s %s)" % (self.lhs, self.op, self.rhs)

class CallExpr:
	def __init__(self, callee, args):
		self.callee = callee
		self.args = args
	def __str__(self):
		return "%s(%s)" % (self.callee, ", ".join(["%s" % a for a in self.args]))
