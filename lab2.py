import lab1
import sys
import os

helpMessage = """
COMP 412, Reference Allocator (lab 2)
Command Syntax:
        ./412alloc k filename [-c] [-h] [-l] [-s] [-v]

Required arguments:
        k        specifies the number of registers available to the allocator
        filename  is the pathname (absolute or relative) to the input file

Optional flags:
        -c        turns of comments in output
        -h        prints this message
        -m        reports MaxLive value to stderr
        -s        initializes undefined uses to zero
        -v        prints out the version number
        -w        suppress warning messages

        -l        Opens log file "./Log" and starts logging.
                  (This flag is additive. More '-l's means more log info.)
"""

def rename(dummy: lab1.IR_Node):
    # test performance difference between using dict vs having maxSR as an input and using arrays
    vrName = 0
    srToVR = {}
    lu = {}

    curr = dummy.prev
    index = curr.lineno
    
    while curr != dummy:
        # for each operand o that curr defines (NOTE: op3 always corresponds to a definition (bc store's op3 is stored in op2))
        o = curr.op3
        if o.sr != -1:  
            if not srToVR.get(o.sr):
                srToVR[o.sr] = vrName
                vrName += 1
            o.vr = srToVR[o.sr]
            o.nu = lu.get(o.sr, float('inf'))
            srToVR[o.sr] = None
            lu[o.sr] = float('inf')

        # for each operand o that curr uses (NOTE: op1 and op2 always refer to uses (bc store's op3 is stored in op2))
        for i in range(1, 3):
            if i == 1:
                o = curr.op1
            elif i == 2:
                o = curr.op2
            if o.sr == -1:  # o.sr == -1 indicates empty operand
                continue    
            if o.isConstant:
                o.vr = o.sr # o.vr is set to o.sr. This may be inefficient, not sure.
                continue
            if not srToVR.get(o.sr):
                srToVR[o.sr] = vrName
                vrName += 1
            o.vr = srToVR[o.sr]
            o.nu = lu.get(o.sr, float('inf'))

        # for each operand o that curr uses
        for i in range(1, 3):
            if i == 1:
                o = curr.op1
            if i == 2:
                o = curr.op2
            lu[o.sr] = index

        index -= 1
        curr = curr.prev
    

def main():
    argc = len(sys.argv)
    xFlag = False
    k = 32  # default value = 32

    if argc != 2 and argc != 3:
        print("ERROR: Too many arguments passed in. Syntax should be ./412fe <flag> <filename>.", file=sys.stderr)
        print(helpMessage)
        exit(0)
    if argc == 2:
        if sys.argv[1] == "-h":
            print(helpMessage)
            return
        filename = sys.argv[1]
    else:
        filename = sys.argv[2]
        if sys.argv[1] == "-x":
            xFlag = True
        elif sys.argv[1].isnumeric():
            k = int(sys.argv[1])
            if k < 3 or k > 64:
                print(f"ERROR: k outside the valid range of [3, 64], the input k was: \'{sys.argv[1]}\'.", file=sys.stderr)
                print(helpMessage)
                exit(0)
        else:
            print(f"ERROR: Command line argument \'{sys.argv[1]}\' not recognized.", file=sys.stderr)
            print(helpMessage)
            exit(0)
    
    # if filename can't be opened, lab1 will print error message and exit cleanly
    dummy = lab1.parse(["lab1.py", filename]) # dummy is the head of the linked list 

    # RENAMING ALGORITHM
    rename(dummy)

    # Print renamed list
    currnode = dummy.next
    while currnode != dummy:
        print(currnode.printWithVRClean())
        currnode = currnode.next

    
if __name__ == "__main__": # if called by the command line, execute main()
    main()
    