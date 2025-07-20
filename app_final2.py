
import streamlit as st
import graphviz
import pandas as pd


# ========== Core DFA Logic ==========

class Node:
    def __init__(self, value, left=None, right=None, nullable=False):
        self.value = value
        self.left = left
        self.right = right
        self.nullable = nullable
        self.firstpos = set()
        self.lastpos = set()
        self.position = None

position_counter = 1
pos_to_symbol = {}
followpos = {}

def build_syntax_tree(regex):
    global position_counter
    stack = []

    def insert_concat(regex):
        result = ""
        operators = {'*', '|', ')'}
        for i in range(len(regex)):
            result += regex[i]
            if regex[i] not in '(|' and i + 1 < len(regex) and regex[i + 1] not in operators:
                result += '.'
        return result

    regex = insert_concat(regex)

    def precedence(op):
        return {'*': 3, '.': 2, '|': 1}.get(op, 0)

    def make_node(op, stack):
        if op == '*':
            a = stack.pop()
            return Node('*', a)
        else:
            b = stack.pop()
            a = stack.pop()
            return Node(op, a, b)

    output = []
    ops = []
    for ch in regex:
        if ch.isalnum() or ch == '#':
            node = Node(ch)
            node.position = position_counter
            pos_to_symbol[position_counter] = ch
            followpos[position_counter] = set()
            node.firstpos = {position_counter}
            node.lastpos = {position_counter}
            node.nullable = False
            position_counter += 1
            output.append(node)
        elif ch == '(':
            ops.append(ch)
        elif ch == ')':
            while ops[-1] != '(':
                output.append(make_node(ops.pop(), output))
            ops.pop()
        else:
            while ops and precedence(ops[-1]) >= precedence(ch):
                output.append(make_node(ops.pop(), output))
            ops.append(ch)

    while ops:
        output.append(make_node(ops.pop(), output))

    return output[0]

def compute_nullable_first_last(node, nullables={}, firstpos_map={}, lastpos_map={}):
    if node.value.isalnum() or node.value == '#':
        return
    if node.value == '|':
        compute_nullable_first_last(node.left, nullables, firstpos_map, lastpos_map)
        compute_nullable_first_last(node.right, nullables, firstpos_map, lastpos_map)
        node.nullable = node.left.nullable or node.right.nullable
        node.firstpos = node.left.firstpos | node.right.firstpos
        node.lastpos = node.left.lastpos | node.right.lastpos
    elif node.value == '.':
        compute_nullable_first_last(node.left, nullables, firstpos_map, lastpos_map)
        compute_nullable_first_last(node.right, nullables, firstpos_map, lastpos_map)
        node.nullable = node.left.nullable and node.right.nullable
        node.firstpos = node.left.firstpos | (node.right.firstpos if node.left.nullable else set())
        node.lastpos = node.right.lastpos | (node.left.lastpos if node.right.nullable else set())
        for i in node.left.lastpos:
            followpos[i] |= node.right.firstpos
    elif node.value == '*':
        compute_nullable_first_last(node.left, nullables, firstpos_map, lastpos_map)
        node.nullable = True
        node.firstpos = node.left.firstpos
        node.lastpos = node.left.lastpos
        for i in node.lastpos:
            followpos[i] |= node.firstpos

def build_dfa(syntax_tree):
    start = frozenset(syntax_tree.firstpos)
    states = {start: 'A'}
    dfa = {}
    marked = set()
    queue = [start]
    name = ord('B')

    while queue:
        current = queue.pop(0)
        if current in marked:
            continue
        marked.add(current)
        transitions = {}
        symbol_map = {}
        for pos in current:
            sym = pos_to_symbol[pos]
            if sym == '#':
                continue
            symbol_map.setdefault(sym, set()).add(pos)
        for sym, positions in symbol_map.items():
            u = set()
            for p in positions:
                u |= followpos[p]
            u = frozenset(u)
            if u not in states:
                states[u] = chr(name)
                name += 1
                queue.append(u)
            transitions[sym] = states[u]
        dfa[states[current]] = transitions
    final_states = [name for state, name in states.items() if any(pos_to_symbol[pos] == '#' for pos in state)]
    return dfa, 'A', final_states

def regex_to_dfa(regex):
    global position_counter, pos_to_symbol, followpos
    position_counter = 1
    pos_to_symbol = {}
    followpos = {}
    regex += '#'  # End marker
    syntax_tree = build_syntax_tree(regex)
    compute_nullable_first_last(syntax_tree)
    dfa, start_state, final_states = build_dfa(syntax_tree)
    return dfa, start_state, final_states, syntax_tree

def visualize_dfa(dfa, start_state, final_states):
    dot = graphviz.Digraph(format='png')
    
    # Set graph and node size attributes to scale down
    dot.attr(size="5,3")                # Shrinks overall graph size (width,height in inches)
    dot.attr('node', fontsize='10')    # Smaller node font
    dot.attr('edge', fontsize='10')    # Smaller edge font
    dot.attr('graph', rankdir='LR')    # Optional: left-to-right layout

    dot.node('', shape='none')
    dot.edge('', start_state)

    for state in dfa:
        shape = "doublecircle" if state in final_states else "circle"
        dot.node(state, shape=shape)

    for from_state, transitions in dfa.items():
        for symbol, to_state in transitions.items():
            dot.edge(from_state, to_state, label=symbol)

    return dot

def visualize_syntax_tree(node, dot=None, counter=[0]):
    if dot is None:
        dot = graphviz.Digraph()
        dot.attr(size="6,4")  # Make overall size smaller
        dot.attr('node', fontsize='10')  # Smaller font
        dot.attr('edge', fontsize='10')
    node_id = str(counter[0])
    label = f"{node.value}"
    if node.position:
        label += f" ({node.position})"
    dot.node(node_id, label)
    current_id = counter[0]
    counter[0] += 1
    if node.left:
        dot = visualize_syntax_tree(node.left, dot, counter)
        dot.edge(str(current_id), str(current_id + 1))
    if node.right:
        prev = counter[0]
        dot = visualize_syntax_tree(node.right, dot, counter)
        dot.edge(str(current_id), str(prev))
    return dot

def simulate_dfa(dfa, start_state, final_states, input_string):
    current = start_state
    for symbol in input_string:
        if symbol not in dfa[current]:
            return False
        current = dfa[current][symbol]
    return current in final_states

# ========== Streamlit App ==========

st.markdown("## 🎯 RE to DFA (Direct Method)")  # Smaller title
st.markdown("### Using Syntax Tree + Firstpos,Lastpos,Followpos,nullable")
st.markdown("### Based on Compiler Design Book")
st.markdown("[📺1. Watch Full Video Tutorial on YouTube : Example1](https://www.youtube.com/watch?v=G8i_2CUHP_Y&t) ")
st.markdown("[📺2. Watch Full Video Tutorial on YouTube : Example2](https://www.youtube.com/watch?v=PsWFuqd2O8c)")
with st.expander("ℹ️ Help:How to Enter Regular Expressions"):
    st.markdown("""
    ### ✅ Regular Expression Input Guide
    - Use `|` for **OR** operations  
      → Example: `(a|b)` means 'a or b'
    - Use `*` for repetition  
      → Example: `(a|b)*` means zero or more repetitions of a or b
    - Do **not** use `+` for OR  
      → ❌ Incorrect: `a+b` (This means "one or more a's followed by b", not a OR b)

    ### 🔍 Sample Regular Expressions
    1. **(a|b)*** → Zero or more a or b  
                
    2. ba(a|b)*ab →  Starts with 'ba', then a or b repeated, ends with 'ab'
    """)
regex_input = st.text_input("Enter Regular Expression:", value="b(a|b)*")

if "dfa_ready" not in st.session_state:
    st.session_state.dfa_ready = False

if st.button("Convert to DFA"):
    try:
        dfa, start, finals, syntax_tree = regex_to_dfa(regex_input)
        st.session_state.dfa = dfa
        st.session_state.start = start
        st.session_state.finals = finals
        st.session_state.syntax_tree = syntax_tree
        st.session_state.dfa_ready = True
        st.success("✅ DFA Constructed!")
    except Exception as e:
        st.session_state.dfa_ready = False
        st.error(f"Error: {str(e)}")

if st.session_state.get("dfa_ready", False):
    
    dfa = st.session_state.dfa
    start = st.session_state.start
    finals = st.session_state.finals
    syntax_tree = st.session_state.syntax_tree

    st.write("#### 🌲 Syntax Tree")
    st.graphviz_chart(visualize_syntax_tree(syntax_tree).source)

    st.subheader("📘 Complete DFA Visualization")
    st.graphviz_chart(visualize_dfa(st.session_state.dfa, st.session_state.start, st.session_state.finals).source)


    with st.expander("Step-by-Step Construction Details"):
        st.subheader("1️⃣ Nullable Values")
        st.write(f"Root Nullable: `{syntax_tree.nullable}`")

        st.subheader("2️⃣ Firstpos")
        st.write(f"`{syntax_tree.firstpos}`")

        st.subheader("3️⃣ Lastpos")
        st.write(f"`{syntax_tree.lastpos}`")

        # Convert dictionary to DataFrame for display
        st.subheader("4️⃣ Followpos")

        # Sample followpos dict for demonstration
        # followpos = {"1": [2], "2": [3,4,5], "3": [3,4,5], "4": [3,4,5], "5": [6], "6": [7], "7": []}

        if followpos:
            try:
                followpos_table = []
                for key, value in followpos.items():
                    node = int(key)
                    fp = ', '.join(str(v) for v in value)
                    followpos_table.append({"Node": node, "followpos": fp})

                df = pd.DataFrame(followpos_table)
                df = df.sort_values(by="Node")

                # ✅ Display without index column
                st.dataframe(df.set_index("Node"))

            except Exception as e:
                st.error(f"❌ Error processing Followpos: {e}")
        else:
            st.warning("⚠️ No followpos data available.")

    st.subheader("🎯 Test String on DFA")
    test_str = st.text_input("Enter string to test:")
    if test_str:
        result = simulate_dfa(dfa, start, finals, test_str)
        st.success("✅ Accepted" if result else "❌ Rejected")
