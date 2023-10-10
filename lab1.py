import sys

#===============================================================================

# Constants

CATEGORIES = ("MEMOP", "LOADI", "ARITHOP", "OUTPUT", "NOP", "CONSTANT",
              "REG", "COMMA", "INTO", "EOF", "EOL") # 11 syntactic categories
MEMOP, LOADI, ARITHOP, OUTPUT, NOP, CONSTANT, REG, COMMA, INTO, EOF, EOL = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10


# Note: for constant and registers, the constant/register # will be stored in the token directly
# The REG and CONSTANT categories will provide this context for us.
LEXEMES = ("load", "store", "loadI", "add", "sub", "mult", "lshift",
            "rshift", "output", "nop", ",", "=>", "", "\\n", "\\r\\n")
LOAD_LEX, STORE_LEX, LOADI_LEX, ADD_LEX, SUB_LEX, MULT_LEX, LSHIFT_LEX, RSHIFT_LEX = 0, 1, 2, 3, 4, 5, 6, 7
OUTPUT_LEX, NOP_LEX, COMMA_LEX, INTO_LEX, EOF_LEX, EOL_LEX, EOL_WINDOWS_LEX = 8, 9, 10, 11, 12, 13, 14

helpMessage = """
COMP 412, Fall 2020, Front End  (lab1_ref)
Command Syntax:
        ./412fe [flags] filename

Required arguments:
        filename  is the pathname (absolute or relative) to the input file

Optional flags:
        -h       prints this message

At most one of the following three flags:
        -s       prints tokens in token stream
        -p       invokes parser and reports on success or failure
        -r       prints human readable version of parser's IR
If none is specified, the default action is '-p'.
"""

#===============================================================================

# Object Type Definitions

class Token:
    category = 0
    lexeme = 0
    def __init__(self, category: int, lexeme: int):
        self.category = category
        self.lexeme = lexeme

class Operand:
    isConstant = False
    sr = -1
    vr = -1
    pr = -1
    nu = -1
    def __init__(self, sr: int, vr = -1, pr = -1, nu = -1):
        self.sr = sr
        self.vr = vr
        self.pr = pr
        self.nu = nu

    def printSR(self):
        if not self.isConstant:
            sr_str = "sr" + str(self.sr) if self.sr != -1 else ""
            # vr_str = "vr" + str(self.vr) if self.vr != -1 else ""
            # pr_str = "pr" + str(self.pr) if self.pr != -1 else ""
            # nu_str = "nu" + str(self.nu) if self.nu != -1 else ""
        else: 
            sr_str = "val " + str(self.sr) if self.sr != -1 else ""
            # vr_str = "val " + str(self.vr) if self.vr != -1 else ""
            # pr_str = "val " + str(self.pr) if self.pr != -1 else ""
            # nu_str = "val " + str(self.nu) if self.nu != -1 else ""
        return f"[ {sr_str} ]" 

    def printVR(self):
        if not self.isConstant:
            vr_str = "vr" + str(self.vr) if self.vr != -1 else ""
        else: 
            vr_str = "val " + str(self.vr) if self.vr != -1 else ""
        return f"[ {vr_str} ]" 

    def printVRClean(self):
        if not self.isConstant:
            vr_str = "r" + str(self.vr) if self.vr != -1 else ""
        else: 
            vr_str = str(self.vr) if self.vr != -1 else ""
        return vr_str

    # def setIsConstant(self, isConstant):
    #     self.isConstant = isConstant


    def getSR(self)->int:
        return self.sr

class IR_Node:
    next = None
    prev = None
    lineno = -1
    opcode = -1 # number because it will be an index into categories
    op1 = None
    op2 = None
    op3 = None
    def __init__(self, lineno: int, opcode: int, sr1: int, sr2: int, sr3: int):
        self.lineno = lineno
        self.opcode = opcode
        self.op1 = Operand(sr1)
        self.op2 = Operand(sr2)
        self.op3 = Operand(sr3)
        # Store information regarding whether op1 is a register or a constant
        if self.opcode == LOADI_LEX or self.opcode == OUTPUT_LEX:
            self.op1.isConstant = True

    def printWithSR(self):
        return f"{LEXEMES[self.opcode]}\t{self.op1.printSR()}, {self.op2.printSR()}, {self.op3.printSR()}"
    
    def printWithVR(self):
        return f"{LEXEMES[self.opcode]}\t{self.op1.printVR()}, {self.op2.printVR()}, {self.op3.printVR()}"

    def printWithVRClean(self):
        op1Str = self.op1.printVRClean()
        op2Str = self.op2.printVRClean()
        op3Str = self.op3.printVRClean()
        if self.opcode == STORE_LEX: # if store operation, then op2 should be printed as rhs (op3)
            temp = op2Str
            op2Str = op3Str
            op3Str = temp

        res = f"{LEXEMES[self.opcode]}\t{op1Str}"
        if op2Str != "":
            res += ", " + op2Str
        if op3Str != "":
            res += " => " + op3Str
        return res
    
    def append(self, dummy):
        self.prev = dummy.prev
        self.next = dummy
        dummy.prev.next = self
        dummy.prev = self

#===============================================================================

# Global Variables
sFlag = False
noerrors = 0
maxSR = -1

#===============================================================================

# Helper functions

def error(lineno, reason):
    print(f"ERROR {lineno}:\t{reason}", file=sys.stderr)
    global noerrors
    noerrors += 1
    
#===============================================================================

# Scanner

"""
Scanner function. Returns a 2-tuple containing the next word's token and lexeme,
and it returns an int representing the new position in the line.

If an error is encountered (e.g., invalid word), it will report the error in stderr and
return ( Token(EOL, EOL_LEX), -1 )
"""
def nextToken(line: str, p: int, lineno: int):
    # eof
    if line == '':
        if sFlag: print(f"{lineno}: < {CATEGORIES[EOF]}, \"{LEXEMES[EOF_LEX]}\" >, {p}")
        return Token(EOF, EOF_LEX), p
    # handle edge case where file ends with a number then EOF
    try: 
        line[p]
    except IndexError: 
        return Token(EOF, EOF_LEX), p

    # skip whitespaces
    while line[p] == ' ' or line[p] == '\t' or line[p] == '\v' or line[p] == '\f':
        p += 1
        # handle edge case where file ends on whitespaces then EOF
        try:
            line[p]
        except IndexError:
            return Token(EOF, EOF_LEX), p

    # add
    if line[p] == 'a':
        p += 1
        if line[p] == 'd':
            p += 1
            if line[p] == 'd':
                p += 1
                if sFlag: print(f"{lineno}: < {CATEGORIES[ARITHOP]}, \"{LEXEMES[ADD_LEX]}\" >, {p}")
                return Token(ARITHOP, ADD_LEX), p   # add
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1

    # newline symbol for both Windows and Linux
    elif line[p] == '\r':
        p += 1
        if line[p] == '\n':
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_WINDOWS_LEX]}\" >, {p}")
            return Token(EOL, EOL_WINDOWS_LEX), p+1
        # else: '\r' is just a whitespace, so ignore and move on
    elif line[p] == '\n':
        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
        return Token(EOL, EOL_LEX), p+1

    # load / loadI / lshift
    elif line[p] == 'l':
        p += 1
        # load / loadI
        if line[p] == 'o':
            p += 1
            if line[p] == 'a':
                p += 1
                if line[p] == 'd':
                    p+= 1
                    if line[p] == 'I':
                        p += 1
                        if sFlag: print(f"{lineno}: < {CATEGORIES[LOADI]}, \"{LEXEMES[LOADI_LEX]}\" >, {p}")
                        return Token(LOADI, LOADI_LEX), p # loadI
                    else:
                        p += 1
                        if sFlag: print(f"{lineno}: < {CATEGORIES[MEMOP]}, \"{LEXEMES[LOAD_LEX]}\" >, {p}")
                        return Token(MEMOP, LOAD_LEX), p # load
                else:
                    
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
           
        # lshift
        elif line[p] == 's':
            p += 1
            if line[p] == 'h':
                p += 1
                if line[p] == 'i':
                    p += 1
                    if line[p] == 'f':
                        p += 1
                        if line[p] == 't':
                            p += 1
                            if sFlag: print(f"{lineno}: < {CATEGORIES[ARITHOP]}, \"{LEXEMES[LSHIFT_LEX]}\" >, {p}")
                            return Token(ARITHOP, LSHIFT_LEX), p   # lshift
                        else:
                            error(lineno, f"\"{line[p]}\" is not a valid word.")
                            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                            return Token(EOL, EOL_LEX), -1
                    else:
                        error(lineno, f"\"{line[p]}\" is not a valid word.")
                        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                        return Token(EOL, EOL_LEX), -1
                else:
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        
    # store, sub
    elif line[p] == 's':
        p += 1
        if line[p] == 't':
            p += 1
            if line[p] == 'o':
                p += 1
                if line[p] == 'r':
                    p += 1
                    if line[p] == 'e':
                        p += 1
                        if sFlag: print(f"{lineno}: < {CATEGORIES[MEMOP]}, \"{LEXEMES[STORE_LEX]}\" >, {p}")
                        return Token(MEMOP, STORE_LEX), p   # store
                    else:
                        error(lineno, f"\"{line[p]}\" is not a valid word.")
                        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                        return Token(EOL, EOL_LEX), -1
                else:
                    
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        elif line[p] == 'u':
            p += 1
            if line[p] == 'b':
                p += 1
                if sFlag: print(f"{lineno}: < {CATEGORIES[ARITHOP]}, \"{LEXEMES[SUB_LEX]}\" >, {p}")
                return Token(ARITHOP, SUB_LEX), p # sub
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1
    
    # mult
    elif line[p] == 'm':
        p += 1
        if line[p] == 'u':
            p += 1
            if line[p] == 'l':
                p += 1
                if line[p] == 't':
                    p += 1
                    if sFlag: print(f"{lineno}: < {CATEGORIES[ARITHOP]}, \"{LEXEMES[MULT_LEX]}\" >, {p}")
                    return Token(ARITHOP, MULT_LEX), p   # mult
                else:
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1
    
    # rshift, register
    elif line[p] == 'r':
        p += 1
        if line[p] == 's':
            p += 1
            if line[p] == 'h':
                p += 1
                if line[p] == 'i':
                    p += 1
                    if line[p] == 'f':
                        p += 1
                        if line[p] == 't':
                            p += 1
                            if sFlag: print(f"{lineno}: < {CATEGORIES[ARITHOP]}, \"{LEXEMES[RSHIFT_LEX]}\" >, {p}")
                            return Token(ARITHOP, RSHIFT_LEX), p   # rshift
                        else:
                            error(lineno, f"\"{line[p]}\" is not a valid word.")
                            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                            return Token(EOL, EOL_LEX), -1
                    else:
                        error(lineno, f"\"{line[p]}\" is not a valid word.")
                        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                        return Token(EOL, EOL_LEX), -1
                else:
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        elif line[p] >= '0' and line[p] <= '9':
            global maxSR
            num = 0
            try:
                while(line[p] >= '0' and line[p] <= '9'):
                    num = num * 10 + int(line[p])
                    p += 1
            except IndexError:
                if sFlag: print(f"{lineno}: < {CATEGORIES[REG]}, \"r{num}\" >, {p}")
                # global maxSR    # ADDED THIS FOR LAB 2
                if num > maxSR: 
                    maxSR = num
                return Token(REG, num), p  # register
            if sFlag: print(f"{lineno}: < {CATEGORIES[REG]}, \"r{num}\" >, {p}")
            # global maxSR    # ADDED THIS FOR LAB 2
            if num > maxSR: 
                maxSR = num
            return Token(REG, num), p  # register
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1

    
    # output
    elif line[p] == 'o':
        p += 1
        if line[p] == 'u':
            p += 1
            if line[p] == 't':
                p += 1
                if line[p] == 'p':
                    p += 1
                    if line[p] == 'u':
                        p += 1
                        if line[p] == 't':
                            p += 1
                            if sFlag: print(f"{lineno}: < {CATEGORIES[OUTPUT]}, \"{LEXEMES[OUTPUT_LEX]}\" >, {p}")
                            return Token(OUTPUT, OUTPUT_LEX), p   # output
                        else:
                            error(lineno, f"\"{line[p]}\" is not a valid word.")
                            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                            return Token(EOL, EOL_LEX), -1
                    else:
                        error(lineno, f"\"{line[p]}\" is not a valid word.")
                        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                        return Token(EOL, EOL_LEX), -1
                else:
                    error(lineno, f"\"{line[p]}\" is not a valid word.")
                    if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                    return Token(EOL, EOL_LEX), -1
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1
    
    # nop
    elif line[p] == 'n':
        p += 1
        if line[p] == 'o':
            p += 1
            if line[p] == 'p':
                p += 1
                return Token(NOP, NOP_LEX), p   # nop
            else:
                error(lineno, f"\"{line[p]}\" is not a valid word.")
                if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
                return Token(EOL, EOL_LEX), -1
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1
    
    # constant (a non-negative integer) # Question: are trailing 0's okay?
    elif line[p] >= '0' and line[p] <= '9':
        num = 0
        try:
            while line[p] >= '0' and line[p] <= '9':
                num = num * 10 + int(line[p])
                p += 1
        # handle edgecase where number is just before EOF
        except IndexError:
            if sFlag: print(f"{lineno}: < {CATEGORIES[CONSTANT]}, \"{num}\" >, {p}")
            return Token(CONSTANT, num), p # constant
        if sFlag: print(f"{lineno}: < {CATEGORIES[CONSTANT]}, \"{num}\" >, {p}")
        return Token(CONSTANT, num), p # constant
    
    # comma
    elif line[p] == ',':
        p += 1
        if sFlag: print(f"{lineno}: < {CATEGORIES[COMMA]}, \"{LEXEMES[COMMA_LEX]}\" >, {p}")
        return Token(COMMA, COMMA_LEX), p # comma
    
    # into
    elif line[p] == '=':
        p += 1
        if line[p] == '>':
            p += 1
            if sFlag: print(f"{lineno}: < {CATEGORIES[INTO]}, \"{LEXEMES[INTO_LEX]}\" >, {p}")
            return Token(INTO, INTO_LEX), p # into
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1
    
    # '//' i.e., comment
    elif line[p] == '/':
        p += 1
        if line[p] == '/':
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1 # comment, so skip the rest of this line
        else:
            error(lineno, f"\"{line[p]}\" is not a valid word.")
            if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
            return Token(EOL, EOL_LEX), -1

    else:
        error(lineno, f"\"{line[p]}\" is not a valid word.")
        if sFlag: print(f"{lineno}: < {CATEGORIES[EOL]}, \"{LEXEMES[EOL_LEX]}\" >, {p}")
        return Token(EOL, EOL_LEX), -1


#===============================================================================

# Parser

# return node if success, None if error
def finish_memop(line: str, p: int, lineno: str, opcode: int):
    sr1, sr2, sr3 = -1, -1, -1

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, "Missing source register in load or store.")
        return None
    sr1 = token.lexeme
    
    token, p = nextToken(line, p, lineno)
    if token.category != INTO:
        error(lineno, f"Missing \'{LEXEMES[INTO_LEX]}\' in load or store.")
        return None

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, "Missing destination register in load or store.")
        return None
    sr3 = token.lexeme
    
    # token, p = nextToken(line, p, lineno)
    # if token.category != EOL:
    #     error(lineno, "Too many operands given to load or store.")
    #     return None

    node = IR_Node(lineno, opcode, sr1, sr2, sr3)
    if opcode == STORE_LEX:
        node.op2.sr = node.op3.sr   # rhs operand of store is assigned to sr2 for renaming algorithm
        node.op3.sr = -1
    return node

# return node if success, None if error
def finish_loadI(line: str, p: int, lineno: str, opcode: int):
    sr1, sr2, sr3 = -1, -1, -1

    token, p = nextToken(line, p, lineno)
    if token.category != CONSTANT:
        error(lineno, "Missing constant in loadI.")
        return None
    sr1 = token.lexeme
    
    token, p = nextToken(line, p, lineno)
    if token.category != INTO:
        error(lineno, f"Missing \'{LEXEMES[INTO_LEX]}\' in load or store.")
        return None

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, "Missing destination register in loadI.")
        return None
    sr3 = token.lexeme
    
    # token, p = nextToken(line, p, lineno)
    # if token.category != EOL:
    #     error(lineno, "Too many operands given to load or store.")
    #     return None

    node = IR_Node(lineno, opcode, sr1, sr2, sr3)
    return node

# return node if success, None if error
def finish_arithop(line: str, p: int, lineno: str, opcode: int):
    sr1, sr2, sr3 = -1, -1, -1

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, f"Missing first source register in {LEXEMES[opcode]}.")
        return None
    sr1 = token.lexeme

    token, p = nextToken(line, p, lineno)
    if token.category != COMMA:
        error(lineno, f"Missing comma in {LEXEMES[opcode]}.")
        return None

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, f"Missing second source register in {LEXEMES[opcode]}.")
        return None
    sr2 = token.lexeme
    
    token, p = nextToken(line, p, lineno)
    if token.category != INTO:
        error(lineno, f"Missing \'{LEXEMES[INTO_LEX]}\' in {LEXEMES[opcode]}.")
        return None

    token, p = nextToken(line, p, lineno)
    if token.category != REG:
        error(lineno, f"Missing destination register in {LEXEMES[opcode]}.")
        return None
    sr3 = token.lexeme
    
    # token, p = nextToken(line, p, lineno)
    # if token.category != EOL:
    #     error(lineno, f"Too many operands given to {LEXEMES[opcode]}.")
    #     return None

    node = IR_Node(lineno, opcode, sr1, sr2, sr3)
    return node

# return node if success, None if error
def finish_output(line: str, p: int, lineno: str, opcode: int) -> IR_Node:
    sr1, sr2, sr3 = -1, -1, -1

    token, p = nextToken(line, p, lineno)
    if token.category != CONSTANT:
        error(lineno, f"Missing constant in {LEXEMES[opcode]}.")
        return None
    sr1 = token.lexeme
    
    # token, p = nextToken(line, p, lineno)
    # if token.category != EOL:
    #     error(lineno, f"Too many operands given to {LEXEMES[opcode]}.")
    #     return None

    node = IR_Node(lineno, opcode, sr1, sr2, sr3)
    return node

# return node if success, None if error
def finish_nop(line: str, p: int, lineno: str, opcode: int):
    sr1, sr2, sr3 = -1, -1, -1

    # token, p = nextToken(line, p, lineno)
    # if token.category != EOL:
    #     error(lineno, f"Too many operands given to {LEXEMES[opcode]}.")
    #     return None

    node = IR_Node(lineno, opcode, sr1, sr2, sr3)
    return node

def parse(argv: list):
    # argc = len(sys.argv)
    argc = len(argv)
    rFlag = False

    if argc != 2 and argc != 3:
        print("ERROR: Too many arguments passed in. Syntax should be ./412fe <flag> <filename>.", file=sys.stderr)
        print(helpMessage)
        exit(0)
    if argc == 2:
        filename = argv[1]
        if argv[1] == "-h":
            print(helpMessage)
            return
    else:
        filename = argv[2]
        flag = argv[1]
        if flag == "-s":
            global sFlag
            sFlag = True
        elif flag == "-r":
            rFlag = True
        elif flag == "-p":
            pass
        else:
            print(f"ERROR: Command line argument \'{flag}\' not recognized.", file=sys.stderr)
            print(helpMessage)
            exit(0)
        

    # Initialize IR_Node list
    dummy = IR_Node(-1, -1, -1, -1, -1)
    dummy.next, dummy.prev = dummy, dummy

    try:
        with open(filename, 'r') as file:
            lineno = 0
            nooperations = 0
            while True: # repeatedly calls readline() until after reaching EOF
                #line = line + " " # Q: he recommends inserting a blank at the end of each line for code simplicity. This isn't O(1) and I don't get benefit
                
                # BEGINNING OF PARSING LOGIC
                line = file.readline() # readline goes at top of while loop so that 1 iteration has '' (for EOF token)
                lineno += 1

                # INVOKE SCANNER
                token, p = nextToken(line, 0, lineno)

                if token.category == EOF: # if EOF reached, no more parsing is necessary
                    break
                elif token.category == EOL or p == -1: # if EOL or error is reached, go to next line
                    continue
                
                if token.category == MEMOP:
                    node = finish_memop(line, p, lineno, token.lexeme)
                    if not node:
                        continue
                elif token.category == LOADI:
                    node = finish_loadI(line, p, lineno, token.lexeme)
                    if not node:
                        continue
                elif token.category == ARITHOP:
                    node = finish_arithop(line, p, lineno, token.lexeme)
                    if not node:
                        continue
                elif token.category == OUTPUT:
                    node = finish_output(line, p, lineno, token.lexeme)
                    if not node:
                        continue
                elif token.category == NOP:
                    node = finish_nop(line, p, lineno, token.lexeme)
                    if not node:
                        continue
                else:
                    error(lineno, f"Operation starts with an invalid opcode: \'{token.lexeme}\'.")
                    continue
                
                # if rFlag:
                #     node.printWithSR()
                node.append(dummy)
                nooperations += 1
    except IOError:
        print(f"ERROR: could not open file {filename} as the input file.", file=sys.stderr)
        exit(0)
            
    if noerrors == 0:
        print(f"//Parse succeeded, finding {nooperations} ILOC operation(s).")
        if rFlag:
            currnode = dummy.next
            while currnode != dummy:
                print(currnode.printWithSR())
                currnode = currnode.next
    else:
        if rFlag:
            print("Due to syntax error, run terminates.")
        else:
            print(f"lab1.py found {noerrors} error(s).")
    global maxSR
    return dummy, maxSR


#===============================================================================
            
if __name__ == "__main__": # if called by the command line, execute parse()
    parse()