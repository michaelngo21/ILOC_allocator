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

# note: the computation of maxLive overshoots it. In reality, I think load operations may kill the register being used, meaning they should be removed from the live set.
def rename(dummy: lab1.IR_Node, maxSR: int):
    # test performance difference between using dict vs having maxSR as an input and using arrays
    vrName = 0
    srToVR = []
    lu = [] # last use
    for i in range(maxSR + 1):
        srToVR.append(None)
        lu.append(float('inf'))

    curr = dummy.prev
    index = curr.lineno

    live = 0
    maxLive = 0
    
    while curr != dummy:
        # for each operand o that curr defines (NOTE: op3 always corresponds to a definition (bc store's op3 is stored in op2))
        o = curr.op3
        if o.sr != -1:  
            if srToVR[o.sr] == None:    # definition without a use, don't count towards maxLive (also: before I used "not srToVR.get(o.sr)", but 0 is considered "falsy")
                srToVR[o.sr] = vrName
                vrName += 1
            # for maxLive >>>
            else:
                live -= 1
            # for maxLive <<<
            o.vr = srToVR[o.sr]
            o.nu = lu[o.sr]
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
            if srToVR[o.sr] == None:
                srToVR[o.sr] = vrName
                vrName += 1
                # for maxLive >>>
                live += 1
                maxLive = max(maxLive, live)
                # for maxLive <<<
            o.vr = srToVR[o.sr]
            o.nu = lu[o.sr]

        # for each operand o that curr uses
        for i in range(1, 3):
            if i == 1:
                o = curr.op1
            if i == 2:
                o = curr.op2
            if o.isConstant:
                continue
            lu[o.sr] = index

        index -= 1
        curr = curr.prev

    return maxLive, vrName
    
# # potentially consider in-lining?
def getAPR(vr: int, nu: int, freePRStack: [], marked: int, reservePR: int, vrToSpillLoc: {}, prToVR: [], prNU: [], vrToPR: [], nextSpillLoc: int)->int:
    if freePRStack:
        print(f"freePRStack contains free PRs: {freePRStack}")
        x = freePRStack.pop()
    else:
        print(f"freePRStack doesn't contain any free PRs: {freePRStack}")
        # pick an unmarked x to spill (based on whichever unmarked PR has latest next use)
        print(f"prNU: {prNU}")
        x = prNU.index(max(prNU))   # potential optimization: don't require 2 passes for choosing PR with latest NU
        print(f"choosing to spill register x: {x}, prNU[x]: {prNU[x]}, prNU: {prNU}")
        
        # only check for marked if marked exists (uses not definitions)
        if marked != -1:
            if x == marked:
                tempCopy = list(prNU)
                tempCopy.pop(x)
                newx = tempCopy.index(max(tempCopy))    # again ^
                if newx >= x:
                    newx += 1
                x = newx                # potential optimization place ^

        nextSpillLoc = spill(x, reservePR, vrToSpillLoc, nextSpillLoc, prToVR, vrToPR)
    vrToPR[vr] = x
    prToVR[x] = vr
    print(f"prNU[x:{x}] = nu:{nu}")
    prNU[x] = nu 

    return x, nextSpillLoc

# def freeAPR(stack: [], pr: int):

def spill(pr, reservePR, vrToSpillLoc, nextSpillLoc, prToVR, vrToPR):
    print("entered spill")
    vr = prToVR[pr]
    vrToSpillLoc[vr] = nextSpillLoc
    nextSpillLoc += 1   # this doesn't work in function form, would need to inline
    # NOTE: since Python doesn't support method overloading, I include the first 4 arguments as formality, but they get tossed out
    loadI_Node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOADI_LEX, pr1=nextSpillLoc, pr2=-1, pr3=reservePR)
    print(loadI_Node.printWithPRClean())
    store_Node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.STORE_LEX, pr1=pr, pr2=-1, pr3=reservePR)
    print(store_Node.printWithPRClean())

    vrToPR[vr] = None
    return nextSpillLoc # need to remember next spillLoc

def restore(vr, pr, reservePR, vrToSpillLoc):
    print("entered restore")
    spillLoc = vrToSpillLoc[vr]
    loadI_Node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOADI_LEX, pr1=spillLoc, pr2=-1, pr3=reservePR)
    print(loadI_Node.printWithPRClean())
    load_Node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOAD_LEX, pr1=pr, pr2=-1, pr3=reservePR)
    print(load_Node.printWithPRClean())
    # it will likely be a good idea to also update vrToPR (similar to how I did in spill)

def allocate(dummy: lab1.IR_Node, k: int, maxVR: int, maxLive: int):
    freePRStack = []
    vrToSpillLoc= {}
    nextSpillLoc = 32768
    reservePR = -1
    if k < maxLive:
        print("k is less than maxLive, so reserving a PR")
        reservePR = k - 1
        k = k - 1   # ensure (k-1)th register isn't considered available (i.e., not added to freePRStack or other PR lists), thus decrement

    vrToPR = [None] * (maxVR + 1)
    prToVR = []
    prNU = []
    for pr in range(k-1, -1, -1):
        prToVR.append(None)
        prNU.append(float('inf'))
        freePRStack.append(pr)    # pop() occurs in GetAPR()
    
    # iterate over the block
    curr = dummy.next
    while curr != dummy:
        marked = -1 # reset marked (NOTE: using a map instead of an array of length k because this makes clear operation more efficient)
        
        # allocate each use u of curr
        for i in range(1, 3):  
            if i == 1:
                u = curr.op1
            if i == 2:
                u = curr.op2
            if u.sr == -1:  # o.sr == -1 indicates empty operand
                continue   
            if u.isConstant:
                u.pr = u.vr # u.pr is set to u.sr since it's not a register, just a constant. This may be inefficient, not sure.
                continue
            pr = vrToPR[u.vr]
            # print(f"pr: {pr}")
            if pr == None:
                ### getAPR >>>
                # if freePRStack:
                #     print(f"freePRStack contains free PRs: {freePRStack}")
                #     x = freePRStack.pop()
                # else:
                #     print(f"freePRStack doesn't contain any free PRs: {freePRStack}")
                #     # pick an unmarked x to spill (based on whichever unmarked PR has latest next use)
                #     x = prNU.index(max(prNU))   # potential optimization: don't require 2 passes for choosing PR with latest NU
                #     print(f"x: {x}, prNU[x]: {prNU[x]}, prNU: {prNU}")
                #     if x == marked:
                #         tempCopy = list(prNU)
                #         tempCopy.pop(x)
                #         newx = tempCopy.index(max(tempCopy))    # again ^
                #         if newx >= x:
                #             newx += 1
                #         x = newx                # potential optimization place ^
                #     nextSpillLoc = spill(x, reservePR, vrToSpillLoc, nextSpillLoc, prToVR)
                # vrToPR[u.vr] = x
                # prToVR[x] = u.vr
                # prNU[x] = u.nu 
                #
                # u.pr = x
                ### getAPR <<<
                print(f"calling getAPR(u.vr={u.vr}, u.nu={u.nu})")
                u.pr, nextSpillLoc = getAPR(u.vr, u.nu, freePRStack, marked, reservePR, vrToSpillLoc, prToVR, prNU, vrToPR, nextSpillLoc)
                print(f"curr.lineno: {curr.lineno}")
                print(f"calling restore(u.vr={u.vr}, u.pr={u.pr}, reservePR={reservePR}, vrToSpillLoc={vrToSpillLoc})")
                restore(u.vr, u.pr, reservePR, vrToSpillLoc)
            else:
                u.pr = pr
            marked = pr
        
        # last use?
        for i in range(1, 3):  
            if i == 1:
                u = curr.op1
            if i == 2:
                u = curr.op2
            if u.nu == float('inf') and prToVR[u.pr] != None:
                ### freeAPR >>>
                print(f"Calling freeAPR({u.pr})")
                vrToPR[prToVR[u.pr]] = None
                prToVR[u.pr] = None
                print(f"prNU[x:{u.pr}] = nu:{float('inf')}")
                prNU[u.pr] = float('inf')
                freePRStack.append(u.pr)
                ### freeAPR <<<
            
        d = curr.op3    # allocate defintions
        if d.sr != -1:  
            # d.pr = getAPR(stack, d.vr, d.nu)
            ### getAPR >>>
            # if freePRStack:
            #     x = freePRStack.pop()
            # else:
            #     # pick an unmarked x to spill (based on whichever PR has latest next use)
            #     x = prNU.index(max(prNU))   # potential optimization: don't require 2 passes for choosing PR with latest NU
            #     nextSpillLoc = spill(x, reservePR, vrToSpillLoc, nextSpillLoc, prToVR)
            # # print(f"vrToPR[d.vr={d.vr}], len(vrToPR): {len(vrToPR)}")
            # vrToPR[d.vr] = x
            # prToVR[x] = d.vr
            # prNU[x] = d.nu 

            # d.pr = x
            ### getAPR <<<
            print(f"calling getAPR(d.vr={d.vr}, d.nu={d.nu})")
            d.pr, nextSpillLoc = getAPR(d.vr, d.nu, freePRStack, -1, reservePR, vrToSpillLoc, prToVR, prNU, vrToPR, nextSpillLoc)

        print(curr.printWithPRClean())

        # TEMPORARY CODE: check whether vrToPR and prToVR match
        for vr in range(len(vrToPR)):
            pr = vrToPR[vr]
            if pr == None:
                continue
            if prToVR[pr] != vr:
                print(f"vrToPR and prToVR don't match! vrToPR[{vr}]: {pr}, but prToVR[{pr}]: {prToVR[pr]}")
        
        # update loop variable
        curr = curr.next


def main():
    argc = len(sys.argv)
    xFlag = False
    mFlag = False
    k = 32  # default value = 32

    if argc < 2 or argc > 4:
        print("ERROR: Invalid number of arguments passed in. Syntax should be ./412alloc k filename [flag]", file=sys.stderr)
        print(helpMessage)
        exit(0)
    if argc == 2:
        if sys.argv[1] == "-h":
            print(helpMessage)
            return
        filename = sys.argv[1]
    else:
        if sys.argv[1].isnumeric():
            k = int(sys.argv[1])
            if k < 3 or k > 64:
                print(f"ERROR: k outside the valid range of [3, 64], the input k was: \'{sys.argv[1]}\'.", file=sys.stderr)
                print(helpMessage)
                exit(0)
        else:
            print(f"ERROR: Command line argument \'{sys.argv[1]}\' not recognized.", file=sys.stderr)
            print(helpMessage)
            exit(0)

        filename = sys.argv[2]
        if argc == 4:
            if sys.argv[3] == "-x":
                xFlag = True
            elif sys.argv[3] == "-m":
                mFlag = True
            else:
                print(f"ERROR: Command line argument \'{sys.argv[3]}\' not recognized.", file=sys.stderr)
                print(helpMessage)
                exit(0)
    
    # if filename can't be opened, lab1 will print error message and exit cleanly
    # TODO: remove "-r"
    dummy, maxSR = lab1.parse(["lab1.py", filename]) # dummy is the head of the linked list 

    # RENAMING ALGORITHM
    maxLive, maxVR = rename(dummy, maxSR)

    # Print renamed list
    if xFlag:
        currnode = dummy.next
        while currnode != dummy:
            print(currnode.printWithVRClean())
            currnode = currnode.next
    
    if mFlag:
        print("maxLive:", maxLive)

    # ALLOCATOR ALGORITHM
    allocate(dummy, k, maxVR, maxLive)

    
if __name__ == "__main__": # if called by the command line, execute main()
    main()
    