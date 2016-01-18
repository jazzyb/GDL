from gdl.error import GDLError


class DatalogError(GDLError):
    pass


class Database(object):
    def __init__(self):
        self.facts = {}
        self.derived_facts = {}
        self.rules = {}
        self.requirements = {}

    ## PUBLIC API

    def define_fact(self, term, arity, args):
        self._sanity_check_fact_arguments(args)
        self.facts.setdefault((term, arity), []).append(args)

    def define_rule(self, term, arity, args, body):
        self._sanity_check_new_rule(term, arity, args, body)
        pred = (term, arity)
        self.rules.setdefault(pred, []).append((args, body))
        self._set_rule_requirements(pred, body)
        self._delete_derived_facts(pred)

    def query(self, ast_head):
        pred = ast_head.predicate
        if pred not in self.facts and pred not in self.rules:
            raise DatalogError(GDLError.NO_PREDICATE % pred, ast_head.token)

        facts = self._find_facts(self.facts.get(pred, []), ast_head.children)
        if facts is True:
            return True
        derived_facts = self._derive_facts(pred, ast_head.children)
        if derived_facts is True:
            return True

        results = facts + derived_facts
        return results if results else False

    ## HELPERS

    def _set_rule_requirements(self, rule, sentences):
        for s in sentences:
            if s.predicate != rule:
                self.requirements.setdefault(s.predicate, set()).add(rule)

    def _delete_derived_facts(self, pred):
        for rule in self._collect_requirements(pred, [pred]):
            self.derived_facts.pop(rule, None)

    def _collect_requirements(self, pred, predicates):
        for rule in self.requirements.get(pred, []):
            if rule not in predicates:
                predicates.append(rule)
                self._collect_requirements(rule, predicates)
        return predicates

    def _find_facts(self, table, query, variables=None):
        results = []
        for args in table:
            match = self._compare_fact(query, args, variables)
            if match is True:
                return True
            elif match:
                results.append(match)
        return results

    def _compare_fact(self, query_args, fact_args, variables=None):
        matches = variables.copy() if variables is not None else {}
        for query, fact in zip(query_args, fact_args):
            if query.is_variable():
                if query.term in matches:
                    if matches[query.term] != fact:
                        return False
                else:
                    matches[query.term] = fact.copy()
            elif query.predicate == fact.predicate:
                if self._compare_fact(query.children, fact.children, matches) is False:
                    return False
            else:
                return False
        return matches if matches else True

    def _derive_facts(self, pred, query):
        if pred not in self.rules:
            return []
        if pred in self.derived_facts:
            return self._find_facts(self.derived_facts[pred], query)
        self._process_rule(pred)
        return self._find_facts(self.derived_facts.get(pred, []), query)

    def _process_rule(self, rule, facts=None, rules=None):
        rules = rules or []
        facts = facts or {}
        nfacts = -1
        while len(facts.get(rule, [])) > nfacts:
            nfacts = len(facts.get(rule, []))
            for args, body in self.rules[rule]:
                variables = self._evaluate_body(body, facts, rules + [rule])
                for fact in self._set_variables(args, variables):
                    if fact not in facts.get(rule, []):
                        facts.setdefault(rule, []).append(fact)
        self.derived_facts[rule] = facts.get(rule, [])

    def _evaluate_body(self, body, facts, rules):
        variables = [None]
        for literal in body:
            variables = self._process_literal(literal, variables, facts, rules)
            if not variables:
                break
        return variables

    def _process_literal(self, literal, variables, facts, rules):
        if literal.is_not():
            literal = literal.children[0]
            return self._evaluate_not(literal, variables, facts, rules)
        elif literal.is_distinct():
            a, b = literal.children
            return self._evaluate_distinct(a, b, variables)
        elif literal.is_or():
            return self._evaluate_or(literal, variables, facts, rules)

        return self._evaluate_literal(literal, variables, facts, rules)

    def _iter_var_results(self, literal, variables, facts, rules):
        pred = literal.predicate
        if self._needs_processing(pred, rules):
            self._process_rule(pred, facts, rules)
        table = self.facts.get(pred, []) + \
                self.derived_facts.get(pred, []) + \
                facts.get(pred, [])
        for var_dict in variables:
            yield self._find_facts(table, literal.children, var_dict), var_dict

    def _needs_processing(self, rule, rules):
        return rule in self.rules and \
               rule not in rules and \
               rule not in self.derived_facts

    def _evaluate_literal(self, literal, variables, facts, rules):
        new_varlist = []
        for results, var_dict in self._iter_var_results(literal, variables, facts, rules):
            if results is True:
                new_varlist.append(var_dict)
            elif results:
                new_varlist.extend(results)
        return new_varlist

    def _evaluate_not(self, literal, variables, facts, rules):
        new_varlist = []
        for results, var_dict in self._iter_var_results(literal, variables, facts, rules):
            assert var_dict
            if not results:
                new_varlist.append(var_dict)
        return new_varlist

    def _evaluate_distinct(self, a, b, variables):
        new_variables = []
        for var_dict in variables:
            acopy = self._vars_to_consts(a.copy(), var_dict)
            bcopy = self._vars_to_consts(b.copy(), var_dict)
            if acopy != bcopy:
                new_variables.append(var_dict)
        return new_variables

    def _evaluate_or(self, or_, variables, facts, rules):
        first, second = or_.children
        first_vars = self._process_literal(first, variables, facts, rules)
        second_vars = self._process_literal(second, variables, facts, rules)
        new_varlist = first_vars[:]
        for var_dict in second_vars:
            if var_dict not in first_vars:
                new_varlist.append(var_dict)
        return new_varlist

    def _set_variables(self, args, variables):
        ret = []
        for var_dict in variables:
            ret.append([self._vars_to_consts(arg.copy(), var_dict) \
                    for arg in args])
        return ret

    def _vars_to_consts(self, node, var_dict):
        if node.is_variable():
            node.token.value = var_dict[node.term].term
        for child in node.children:
            self._vars_to_consts(child, var_dict)
        return node

    def _sanity_check_fact_arguments(self, args):
        if type(args) is not list:
            raise TypeError('fact arguments should be a list')
        for arg in args:
            if arg.arity > 0:
                self._sanity_check_fact_arguments(arg.children)
            if arg.is_variable():
                raise DatalogError(GDLError.FACT_VARIABLE, arg.token)

    def _sanity_check_new_rule(self, term, arity, args, body):
        pass # TODO
