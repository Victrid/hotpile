import json
import sys
from itertools import product
from os import remove, system
from os.path import abspath, dirname, join
from typing import Union


class Reference:
    def __init__(self, number, not_exclude):
        self.number = number
        self.not_exclude = not_exclude

    def __repr__(self):
        return f"->{'' if self.not_exclude else '^'}{self.number}"


class StateGenerator:
    def __init__(self):
        self.internal_state_count = 0
        self.line_name = {}
        self.accept_line = ""
        self.reject_line = ""

    def load_line(self, line):
        t = line.strip().split()
        if len(t) <= 2:
            raise Exception("Invalid function line")
        self.line_name[t[0]] = t[1]

    def generate_subroutine(self, caller_line_no, callee):
        self.internal_state_count += 1
        return "{}_{}_substate({})".format( callee, caller_line_no, self.internal_state_count)

    def generate_line(self, line_no):
        if line_no == self.accept_line:
            return "ACCEPT"
        elif line_no == self.reject_line:
            return "REJECT"
        else:
            return "{}_{}".format(self.line_name[line_no], line_no)


class Function:
    def __init__(self, function_definition: dict, total_tape: int, all_symbol: list[str],
                 state_generator: StateGenerator):
        self.function_definition = function_definition
        self.tape_length = len(self.function_definition["config"]["tape"])
        self.total_tape = total_tape
        self.state_generator = state_generator
        self.all_symbol = all_symbol
        self.states = None

    def load_states(self, code_segment):
        if self.states is None:
            self.states = set()
            for item in code_segment:
                self.states.add(item.start_state)
                self.states.add(item.end_state)
            if self.function_definition["config"]["in_state"] not in self.states:
                raise Exception(
                        "Start state {} not found in the code segment".format(
                                self.function_definition["config"]["in_state"]
                                )
                        )
            for state in self.function_definition["config"]["out_state"]:
                if state not in self.states:
                    raise Exception("End state {} not found in the code segment".format(state))

    def get_instance(self, caller_line_no: str, start_state: str, end_state: list[str], pseudo_list: dict,
                     tape: list[int]) -> list[tuple[str, str]]:
        if "pseudo" in self.function_definition["config"]:
            required_pseudo = self.function_definition["config"]["pseudo"]
        else:
            required_pseudo = []
        for item in required_pseudo:
            if item not in pseudo_list:
                raise Exception("Pseudo {} not found in pseudo-list".format(item))

        code_segment = [
            Code(item, pseudo_list, self.function_definition, self.all_symbol) for item in
            self.function_definition["code"]
            ]

        self.load_states(code_segment)

        if len(end_state) != len(self.function_definition["config"]["out_state"]):
            raise Exception("End state list is not equal to the one in the function")

        if len(tape) != self.tape_length:
            raise ValueError("Tape length is not equal to the one in the function")

        tape_index = tape

        state_lookup_table = {self.function_definition["config"]["in_state"]: start_state}
        for out_a, out_b in zip(self.function_definition["config"]["out_state"], end_state):
            state_lookup_table[out_a] = out_b
        for item in self.states:
            if item not in state_lookup_table:
                state_lookup_table[item] = self.state_generator.generate_subroutine(caller_line_no,
                                                                                    self.function_definition["name"]
                                                                                    )
        out_str = [("", "// Call of {}".format(self.function_definition["name"]),)]
        for item in code_segment:
            item.fill_in_tape(state_lookup_table[item.start_state], state_lookup_table[item.end_state], tape_index,
                              self.total_tape
                              )
            out_str += item.convert()
        out_str += [("// End call of {}".format(self.function_definition["name"]), "",)]
        return out_str


class Code:
    def __init__(self, code_list: list[str], pseudo_list: dict, function: dict, all_symbol: list[str]):
        self.pseudo_list = pseudo_list
        self.tape_length = len(function["config"]["tape"])
        self.code_list = code_list
        self.all_symbol = all_symbol
        self.filled = False
        self.prior = []

        if len(self.code_list) != 2 + 3 * self.tape_length:
            raise Exception("Invalid code length")

        process_dict = {
            "start_state": self.code_list[0],
            "match":       self.code_list[1:1 + self.tape_length],
            "end_state":   self.code_list[1 + self.tape_length],
            "edit":        self.code_list[2 + self.tape_length:2 + 2 * self.tape_length],
            "move":        self.code_list[2 + 2 * self.tape_length:2 + 3 * self.tape_length]
            }

        # start state and end state
        st_t = process_dict["start_state"].split()
        if len(st_t) != 2 or st_t[0] != "SYMBOL":
            raise Exception("Invalid start state")
        self.start_state = st_t[1]

        st_t = process_dict["end_state"].split()
        if len(st_t) != 2 or st_t[0] != "SYMBOL":
            raise Exception("Invalid end state")
        self.end_state = st_t[1]

        # matches
        match_list = []
        for item in process_dict["match"]:
            u = item.split()
            if u[0] == "SYMBOL":
                if len(u[1]) != 1 or u[1] not in self.all_symbol:
                    raise Exception("Invalid symbol for matching")
                match_list.append((u[1],))
            elif u[0] == "PSEUDO" or u[0] == "GPSEUDO":
                if len(u) != 2 or u[1] not in self.pseudo_list:
                    raise Exception("Invalid pseudo for matching")
                match_list.append((self.pseudo_list[u[1]],))
            elif u[0] == "NPSEUDO":
                if len(u) != 2 or u[1] not in self.pseudo_list:
                    raise Exception("Invalid pseudo for matching")
                match_list.append(tuple(self.get_reverse([self.pseudo_list[u[1]]])))
            elif u[0] == "LIST":
                if len(u) != 2:
                    raise Exception("Invalid list for matching")
                match_list.append(tuple(u[1]))
            elif u[0] == "NLIST":
                if len(u) != 2:
                    raise Exception("Invalid list for matching")
                match_list.append(tuple(self.get_reverse(list(u[1]))))
            elif u[0] == "SPECIAL":
                if len(u) != 2:
                    raise Exception("Invalid special for matching")
                if u[1].isnumeric():
                    match_list.append((Reference(int(u[1]), False),))
                elif u[1] == "any":
                    match_list.append(tuple(self.all_symbol))
            elif u[0] == "GSPECIAL":
                if len(u) != 2:
                    raise Exception("Invalid special for matching")
                if u[1].isnumeric():
                    match_list.append((Reference(int(u[1]), True),))
                elif u[1] == "any":
                    match_list.append(tuple(self.all_symbol))
            elif u[0] == "NSPECIAL":
                if len(u) != 2:
                    raise Exception("Invalid special for matching")
                if u[1].isnumeric():
                    match_list.append((Reference(int(u[1]), False),))
                elif u[1] == "any":
                    match_list.append(tuple())
            else:
                raise Exception("Invalid matching")

        total_list = match_list
        edit_list = []
        for item in process_dict["edit"]:
            u = item.split()
            if u[0] == "SYMBOL":
                if len(u[1]) != 1 or u[1] not in self.all_symbol:
                    raise Exception("Invalid symbol for matching")
                edit_list.append((u[1],))
                total_list.append((u[1],))
            elif u[0] == "PSEUDO" or u[0] == "GPSEUDO":
                if len(u) != 2 or u[1] not in self.pseudo_list or self.pseudo_list[u[1]] not in self.all_symbol:
                    raise Exception("Invalid pseudo for matching")
                edit_list.append((self.pseudo_list[u[1]],))
                total_list.append((self.pseudo_list[u[1]],))
            elif u[0] == "NPSEUDO":
                if len(u) != 2 or u[1] not in self.pseudo_list or self.pseudo_list[u[1]] not in self.all_symbol:
                    raise Exception("Invalid pseudo for matching")
                edit_list.append(tuple(self.get_reverse([self.pseudo_list[u[1]]])))
                total_list.append(tuple(self.get_reverse([self.pseudo_list[u[1]]])))
            elif u[0] == "SPECIAL":
                if len(u) != 2:
                    raise Exception("Invalid special for matching")
                if u[1].isnumeric() and int(u[1]) < len(match_list):
                    edit_list.append((Reference(int(u[1]), True),))
                    total_list.append((Reference(int(u[1]), True),))
                else:
                    raise Exception("Invalid special for matching")
            else:
                raise Exception("Invalid edit for matching")

        self.match_list: list[Union[tuple[str, ...], tuple[Reference]]] = match_list
        self.edit_list = edit_list

        self.move_list = []
        for item in process_dict["move"]:
            u = item.split()
            if len(u) != 2:
                raise Exception("Invalid move for matching")
            if u[0] == "SYMBOL":
                if u[1] not in ["<", ">", "-"]:
                    raise Exception("Invalid move for matching")
                self.move_list.append(u[1])
            elif u[0] == "PSEUDO":
                if u[1] not in self.pseudo_list:
                    raise Exception("Invalid pseudo for matching")
                if self.pseudo_list[u[1]] not in ["<", ">", "-"]:
                    raise Exception("Invalid move for matching")
                self.move_list.append(self.pseudo_list[u[1]])

    def get_reverse(self, content: list[str]) -> list[str]:
        return list(set(self.all_symbol) - set(content))

    def fill_in_tape(self, start_state, end_state, tape_index: list[int], tape_total: int):
        if self.filled:
            raise Exception("Tape already filled")

        if len(tape_index) != self.tape_length:
            raise Exception("Invalid tape length")

        self.tape_length = tape_total
        self.start_state = start_state
        self.end_state = end_state

        dest_match_list: list[Union[tuple[Reference], tuple[str, ...]]] = [tuple(self.all_symbol)] * tape_total
        dest_edit_list: list[Union[tuple[Reference], tuple[str, ...]]] = [(Reference(i, True),) for i in
                                                                          range(tape_total)]
        dest_move_list = ["-"] * tape_total

        directional = list(range(tape_total))
        for index, position in enumerate(tape_index):
            directional[index] = position

        self.prior = tape_index

        for index, content in zip(tape_index, self.match_list):
            dest_match_list[index] = content
            if len(content) == 1 and type(content[0]) is Reference:
                ref = content[0]
                ref.number = directional[ref.number]
                dest_match_list[index] = (ref,)
        for index, content in zip(tape_index, self.edit_list):
            dest_edit_list[index] = content
            if len(content) == 1 and type(content[0]) is Reference:
                ref = content[0]
                ref.number = directional[ref.number]
                dest_edit_list[index] = (ref,)
        for index, content in zip(tape_index, self.move_list):
            dest_move_list[index] = content

        self.match_list = dest_match_list
        self.edit_list = dest_edit_list
        self.move_list = dest_move_list

        self.filled = True
        return

    def write_rules(self, *args) -> list[tuple[str, str]]:
        if not self.filled:
            raise Exception("Tape not filled")
        if len(args) != 2 + 3 * self.tape_length:
            raise Exception("Invalid rule")

        # Resolve reference
        whole_list = args[1:1 + self.tape_length] + args[2 + self.tape_length:2 + 2 * self.tape_length]
        list_expanded = [whole_list]
        for index in self.prior + list(range(self.tape_length)):
            new_list = []
            for list_prim in list_expanded:
                general_list = []
                for item in list_prim:
                    if type(item) is str:
                        general_list.append((item,))
                    elif type(item) is Reference and item.number == index and item.not_exclude:
                        assert type(list_prim[index]) is str
                        general_list.append((list_prim[index],))
                    elif type(item) is Reference and item.number == index and not item.not_exclude:
                        assert type(list_prim[index]) is str
                        general_list.append(tuple(self.get_reverse([list_prim[index]])))
                    else:
                        general_list.append((item,))
                for new_gen_tuple in product(*general_list):
                    new_list.append(list(new_gen_tuple))

            list_expanded = new_list

        final = []
        for item in list_expanded:
            process_dict = {
                "start_state": args[0],
                "match":       item[0:self.tape_length],
                "end_state":   args[1 + self.tape_length],
                "edit":        item[self.tape_length:2 * self.tape_length],
                "move":        args[2 + 2 * self.tape_length:2 + 3 * self.tape_length],
                }

            out_str_1 = ""
            out_str_1 += process_dict["start_state"]
            for item in process_dict["match"]:
                out_str_1 += ",{}".format(item)
            out_str_2 = ""
            out_str_2 += process_dict["end_state"]
            for item in process_dict["edit"]:
                out_str_2 += ",{}".format(item)
            for item in process_dict["move"]:
                out_str_2 += ",{}".format(item)
            final += [(out_str_1, out_str_2,)]

        return final

    def convert(self) -> list[tuple[str, str]]:
        if not self.filled:
            raise Exception("Tape not filled")
        command_group = list(product([self.start_state], *self.match_list, [self.end_state], *self.edit_list,
                                     *self.move_list
                                     )
                             )
        out_str = []
        for item in command_group:
            out_str += self.write_rules(*item)
        return out_str


class MainCall:
    def __init__(self, filename):
        output_lines = []
        with open(filename, "r") as f:
            lines = f.readlines()

        self.all_symbol = []
        self.functions: dict[str, Function] = {}
        self.tape = []

        self.accept_state = ""
        self.reject_state = ""
        self.start_state = ""

        self.output: list[str] = []
        self.state_gen = StateGenerator()

        for line in lines:
            self.output += ["// {}".format(line.strip())]

        name = ""
        for line in lines:
            if line.strip() == "":
                continue
            elif "%%" in line:
                # Processor function
                t = line.strip().split()
                if t[1] == "NAME":
                    name = " ".join(t[2:])
                elif t[1] == "START":
                    self.start_state = t[2]
                elif t[1] == "ACCEPT":
                    self.accept_state = t[2]
                elif t[1] == "REJECT":
                    self.reject_state = t[2]
                elif t[1] == "TAPE":
                    self.tape = t[2:]
                elif t[1] == "SYMBOL":
                    self.all_symbol += t[2:]
                elif t[1] == "USE":
                    self.output += ["// Used Function: "]
                    self.output += self.register_functions(filename, t[2])
                    self.output += [""]
                else:
                    raise Exception("Invalid function")
            elif line[0] == "#":
                continue
            else:
                output_lines.append(line)

        self.output.append("name: {}".format(name))
        self.output.append("accept: ACCEPT")

        for line in output_lines:
            self.state_gen.load_line(line)

        if self.start_state in self.state_gen.line_name:
            self.output += ["init: {}".format(self.state_gen.generate_line(self.start_state))]
        else:
            self.output += ["init: REJECT"]

        self.state_gen.accept_line = self.accept_state
        self.state_gen.reject_line = self.reject_state

        self.output += ["// PROGRAM START"]
        for line in output_lines:
            function = self.process_function_line(line)
            for start, end in function:
                self.output += [start, end]
        self.output += ["// PROGRAM END"]

    def write(self):
        for item in self.output:
            print(item)

    def register_functions(self, caller: str, filename: str) -> list[str]:
        srcname = join(abspath(dirname(caller)), filename)
        parser = join(abspath(dirname(__file__)), "parser")
        parsed_file = join(abspath(dirname(caller)), "{}.json".format(filename))
        system("cat '{}' | '{}' > '{}'".format(srcname, parser, parsed_file))
        with open(parsed_file) as f:
            function_json = json.load(f)
        remove(parsed_file)
        for function in function_json:
            self.functions[function["name"]] = Function(function, len(self.tape), self.all_symbol, self.state_gen)
        with open(srcname) as f:
            out_string = f.read()

        out_strings = [ "// file: {}".format(filename)]

        for item in out_string.splitlines():
            out_strings.append("// {}".format(item))
        return out_strings

    def process_function_line(self, line: str) -> list[tuple[str, str]]:
        t = line.strip().split()
        start_state = self.state_gen.generate_line(t[0])
        function = t[1]
        parameters = "".join(t[2:]).strip()
        if parameters[0] != "[" or parameters[-1] != ']':
            raise Exception("Invalid parameters")
        parameters = parameters[1:-1]
        u = list(filter(lambda x: x != "", parameters.split(";")))
        if len(u) < 2 or len(u) > 3:
            raise Exception("Invalid parameters")

        tape_series = list(filter(lambda x: x != "", u[0].split(",")))
        for tape in tape_series:
            if tape not in self.tape:
                raise Exception("Invalid tape")
        tape_index = [self.tape.index(tape) for tape in tape_series]

        end_state_number = list(filter(lambda x: x != "", u[1].split(",")))
        end_states = [self.state_gen.generate_line(i) for i in end_state_number]

        pseudo_list = {}
        if len(u) == 3:
            pseudo_series = list(filter(lambda x: x != "", u[2].split(",")))

            for pseudo in pseudo_series:
                r = pseudo.split("=")
                if len(r) != 2:
                    raise Exception("Invalid pseudo")
                pseudo_list[r[0]] = r[1]

        return self.functions[function].get_instance(t[0], start_state, end_states, pseudo_list, tape_index)


def main(filename):
    u = MainCall(filename)
    u.write()


if __name__ == "__main__":
    main(sys.argv[1])
