import lab1
import sys

helpMessage = """
COMP 412, Allocator (lab 2)
Command Syntax:
        ./412alloc k filename <flag>

Required arguments:
        k        specifies the number of registers available to the allocator
        filename  is the pathname (absolute or relative) to the input file

Optional flags:
        -h        prints this message
        -m        reports MaxLive value to stdout
        -x        prints the renamed list before register allocation
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
            # print(f"RENAMING: o.vr:{o.vr}, o.nu:{o.nu}")
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
            if o.isConstant or o.sr == -1:
                continue
            # print(f"RENAMING: about to set lu[o.sr:{o.sr}] = {index}")
            lu[o.sr] = index

        index -= 1
        curr = curr.prev

    # print(f"// maxLive is {maxLive}")
    return maxLive, vrName
    
# # potentially consider in-lining?
def getAPR(vr: int, nu: int, freePRStack: [], marked: int, reservePR: int, vrToSpillLoc: {}, prToVR: [], prNU: [], vrToPR: [], nextSpillLoc: int, curr:lab1.IR_Node)->int:
    # print(f"//freePRStack: {freePRStack}")
    # print(f"//prToVR: {prToVR}")
    if freePRStack:
        # print(f"freePRStack contains free PRs: {freePRStack}")
        x = freePRStack.pop()
    else:
        # print(f"time to spill spill with vr={vr} b/c freePRStack doesn't contain any free PRs: {freePRStack}")
        # pick an unmarked x to spill (based on whichever unmarked PR has latest next use)
        # print(f"prNU: {prNU}")
        x = prNU.index(max(prNU))   # potential optimization: don't require 2 passes for choosing PR with latest NU
        # print(f"//choosing to spill register x: {x}") #, prNU[x]: {prNU[x]}, prNU: {prNU}")
        
        # only check for marked if marked exists (uses not definitions)
        if marked != -1:
            # print(f"//marked: {marked}, x: {x}")
            if x == marked:
                tempCopy = list(prNU)
                tempCopy.pop(x)
                newx = tempCopy.index(max(tempCopy))    # again ^
                if newx >= x:
                    newx += 1
                x = newx                # potential optimization place ^
                # print(f"//x was marked, so we instead picked newx: {x}, prNU[x]: {prNU[x]}, prNU: {prNU}")

        nextSpillLoc = spill(x, reservePR, vrToSpillLoc, nextSpillLoc, prToVR, vrToPR, curr)
    vrToPR[vr] = x
    prToVR[x] = vr
    # print(f"//prNU[x:{x}] = nu:{nu}")
    prNU[x] = nu 

    # print(f"//getAPR returning: {x}, {nextSpillLoc}")
    return x, nextSpillLoc

def freeAPR(pr, freePRStack, vrToPR, prToVR, prNU):
    vrToPR[prToVR[pr]] = None
    prToVR[pr] = None
    prNU[pr] = float('inf')
    freePRStack.append(pr)

def spill(pr, reservePR, vrToSpillLoc, nextSpillLoc, prToVR, vrToPR, curr:lab1.IR_Node):
    # print(f"entered spill with pr:{pr} which associates to vr:{prToVR[pr]}, which will get the nextSpillLoc:{nextSpillLoc}")
    vr = prToVR[pr]
    # if there is no memory location for VR already (it hasn't already been stored), then use the nextSpillLoc
    if vrToSpillLoc.get(vr) == None:
        vrToSpillLoc[vr] = nextSpillLoc
        nextSpillLoc += 4   # NOTE: addresses are word-aligned, so must be multiples of 4
        # NOTE: since Python doesn't support method overloading, I include the first 4 arguments as formality, but they get tossed out
        loadI_node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOADI_LEX, pr1=vrToSpillLoc[vr], pr2=-1, pr3=reservePR)
        lab1.IR_Node.insertBefore(curr, loadI_node) # print(loadI_Node.printWithPRClean())
        # NOTE: recall that for store, what should go into pr3 should actually be stored in pr2 because it's a use. Printing the node with this structure leads to correct output
        store_node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.STORE_LEX, pr1=pr, pr2=reservePR, pr3=-1)
        lab1.IR_Node.insertBefore(curr, store_node)

    vrToPR[vr] = None
    return nextSpillLoc # need to remember next spillLoc

def restore(vr, pr, reservePR, vrToPR:[], vrToSpillLoc:[], curr:lab1.IR_Node):
    # print(f"entered restore with vr:{vr} which associates to spillLoc:{vrToSpillLoc[vr]}, and the value at this address will be stored in pr:{pr}")
    spillLoc = vrToSpillLoc[vr]
    loadI_node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOADI_LEX, pr1=spillLoc, pr2=-1, pr3=reservePR)
    lab1.IR_Node.insertBefore(curr, loadI_node) # print(loadI_Node.printWithPRClean())
    load_node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOAD_LEX, pr1=reservePR, pr2=-1, pr3=pr)
    lab1.IR_Node.insertBefore(curr, load_node)
    # print(load_Node.printWithPRClean())
    # note: unnecessary to update vrToPR because that's done in getAPR

def allocate(dummy: lab1.IR_Node, k: int, maxVR: int, maxLive: int):
    freePRStack = []
    vrToSpillLoc = {}
    nextSpillLoc = 32768
    vrToLoadIConst = {}
    reservePR = -1
    if k < maxLive:
        # print("k is less than maxLive, so reserving a PR")
        reservePR = k - 1
        k = k - 1   # ensure (k-1)th register isn't considered available (i.e., not added to freePRStack or other PR lists), thus decrement

    vrToPR = [None] * (maxVR + 1)
    prToVR = []
    prNU = []
    for pr in range(k-1, -1, -1):
        prToVR.append(None)
        prNU.append(float('inf'))
        freePRStack.append(pr)    # pop() occurs in GetAPR
    
    # iterate over the block
    curr = dummy.next
    while curr != dummy:
        marked = -1 # reset marked (NOTE: using a map instead of an array of length k because this makes clear operation more efficient)
        if curr.opcode == lab1.LOADI_LEX:
            # print(f"entered loadI case: vrToLoadIConst[curr.op3.vr:{curr.op3.vr}] = curr.op1.sr:{curr.op1.sr}")
            vrToLoadIConst[curr.op3.vr] = curr.op1.sr # Note that the constant value is stored in op1.sr (and potentially op1.vr as well--I forgot rename implementation)
            lab1.IR_Node.remove(curr)
            curr = curr.next    # note: even though curr has been removed, it's next field remains unchanged
            continue

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
                # print(f"calling getAPR(u.vr={u.vr}, u.nu={u.nu})")
                u.pr, nextSpillLoc = getAPR(u.vr, u.nu, freePRStack, marked, reservePR, vrToSpillLoc, prToVR, prNU, vrToPR, nextSpillLoc, curr)
                # if rematerializable (loadI)
                if u.vr in vrToLoadIConst:    
                    loadI_Node = lab1.IR_Node(lineno=-1, sr1=-1, sr2=-1, sr3=-1, isSpillOrRestore=True, opcode=lab1.LOADI_LEX, pr1=vrToLoadIConst[u.vr], pr2=-1, pr3=u.pr)
                    lab1.IR_Node.insertBefore(curr, loadI_Node)
                    # freeAPR(u.pr, freePRStack, vrToPR, prToVR, prNU)
                # if not rematerializable
                else:   
                    # print(f"calling restore(u.vr={u.vr}, u.pr={u.pr}, reservePR={reservePR}, vrToSpillLoc={vrToSpillLoc})")
                    restore(u.vr, u.pr, reservePR, vrToPR, vrToSpillLoc, curr)
            else:
                u.pr = pr
            # print(f"//marked set to u.pr = {u.pr}")
            marked = u.pr
        
        # last use?
        for i in range(1, 3):  
            if i == 1:
                u = curr.op1
            if i == 2:
                u = curr.op2

            # If this is the last use OR is rematerializable
            if (u.nu == float('inf')  or u.vr in vrToLoadIConst) and prToVR[u.pr] != None:
                # print(f"last use (or rematerialization) so calling freeAPR({u.pr}). The corresponding VR is {prToVR[u.pr]}")
                freeAPR(u.pr, freePRStack, vrToPR, prToVR, prNU)
                # print(f"freePRStack: {freePRStack}")
            
        d = curr.op3    # allocate defintions
        if d.sr != -1:  
            # print(f"calling getAPR(d.vr={d.vr}, d.nu={d.nu})")
            d.pr, nextSpillLoc = getAPR(d.vr, d.nu, freePRStack, -1, reservePR, vrToSpillLoc, prToVR, prNU, vrToPR, nextSpillLoc, curr)
            # definition never used?
            if d.nu == float('inf'):    
                # print(f"definition with no use for vr={prToVR[d.pr]}, so freeing pr={d.pr}")
                freeAPR(d.pr, freePRStack, vrToPR, prToVR, prNU)
                

        # print(curr.printWithPRClean())

        # TEMPORARY CODE: check whether vrToPR and prToVR match
        # for vr in range(len(vrToPR)):
        #     pr = vrToPR[vr]
        #     if pr == None:
        #         continue
        #     if prToVR[pr] != vr:
        #         print(f"vrToPR and prToVR don't match! vrToPR[{vr}]: {pr}, but prToVR[{pr}]: {prToVR[pr]}")
        # for pr in range(len(prToVR)):
        #     vr = prToVR[pr]
        #     if vr == None:
        #         continue
        #     if vrToPR[vr] != pr:
        #         print(f"vrToPR and prToVR don't match! vrToPR[{vr}]: {pr}, but prToVR[{pr}]: {prToVR[pr]}")

        # TEMPORARY CODE: look into vrToSpillLoc
        # print(f"vrToSpillLoc: {vrToSpillLoc}")
        # print(f"prToVR: {prToVR}")
        # print(f"vrToPR: {vrToPR}")
        
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
        print("//maxLive:", maxLive)

    # ALLOCATOR ALGORITHM
    allocate(dummy, k, maxVR, maxLive)

    currnode = dummy.next
    while currnode != dummy:
        print(currnode.printWithPRClean())
        currnode = currnode.next

    
if __name__ == "__main__": # if called by the command line, execute main()
    main()
    