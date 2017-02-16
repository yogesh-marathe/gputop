#!/usr/bin/env python2

# Copyright (C) 2015-2016 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Generates code for metric sets supported by the drm i915-perf driver
# including:
#
# - Static arrays describing the various NOA/Boolean/OA register configs
# - Functions/structs for advertising metrics via sysfs
# - Code that can evaluate which configs are available for the current system
#   based on the RPN availability equations
#


import xml.etree.ElementTree as ET
from operator import itemgetter
import argparse
import sys
import re
import copy
import hashlib

default_set_blacklist = {}

def underscore(name):
    s = re.sub('MHz', 'Mhz', name)
    s = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s).lower()

def print_err(*args):
    sys.stderr.write(' '.join(map(str,args)) + '\n')

c_file = None
_c_indent = 0

def c(*args):
    if c_file:
        code = ' '.join(map(str,args))
        for line in code.splitlines():
            indent = ''.rjust(_c_indent).replace('        ', '\t')
            text = indent + line
            c_file.write(text.rstrip() + "\n")

def c_indent(n):
    global _c_indent
    _c_indent = _c_indent + n
def c_outdent(n):
    global _c_indent
    _c_indent = _c_indent - n

header_file = None
_h_indent = 0

def h(*args):
    if header_file:
        code = ' '.join(map(str,args))
        for line in code.splitlines():
            indent = ''.rjust(_c_indent).replace('        ', '\t')
            text = indent + line
            header_file.write(text.rstrip() + "\n")

def h_indent(n):
    _h_indent = _h_indent + n
def h_outdent(n):
    _h_indent = _h_indent - n


# Tries to avoid fragility from ET.tostring() by normalizing into CSV string first
# FIXME: avoid copying between scripts!
def get_v2_config_hash(metric_set):
    registers_str = ""
    for config in metric_set.findall(".//register_config"):
        if config.get('id') == None:
            config_id = '0'
        else:
            config_id = config.get('id')
        if config.get('priority') == None:
            config_priority = '0'
        else:
            config_priority = config.get('priority')
        if config.get('availability') == None:
            config_availability = ""
        else:
            config_availability = config.get('availability')
        for reg in config.findall("register"):
            addr = int(reg.get('address'), 16)
            value = int(reg.get('value'), 16)
            registers_str = registers_str + config_id + ',' + config_priority + ',' + config_availability + ',' + str(addr) + ',' + str(value) + '\n'

    return hashlib.md5(registers_str).hexdigest()


def brkt(subexp):
    if " " in subexp:
        return "(" + subexp + ")"
    else:
        return subexp

def splice_bitwise_and(args):
    return brkt(args[1]) + " & " + brkt(args[0])

def splice_logical_and(args):
    return brkt(args[1]) + " && " + brkt(args[0])

def splice_ult(args):
    return brkt(args[1]) + " < " + brkt(args[0])

def splice_ugte(args):
    return brkt(args[1]) + " >= " + brkt(args[0])

exp_ops = {}
#                 (n operands, splicer)
exp_ops["AND"]  = (2, splice_bitwise_and)
exp_ops["UGTE"] = (2, splice_ugte)
exp_ops["ULT"]  = (2, splice_ult)
exp_ops["&&"]   = (2, splice_logical_and)


c_syms = {}
c_syms["$SliceMask"] = "INTEL_INFO(dev_priv)->sseu.slice_mask"
c_syms["$SubsliceMask"] = "INTEL_INFO(dev_priv)->sseu.subslice_mask"
c_syms["$SkuRevisionId"] = "dev_priv->drm.pdev->revision"

mnemonic_syms = {}
mnemonic_syms["$SliceMask"] = "slices"
mnemonic_syms["$SubsliceMask"] = "subslices"
mnemonic_syms["$SkuRevisionId"] = "sku"

copyright = """/*
 * Autogenerated file, DO NOT EDIT manually!
 *
 * Copyright (c) 2015 Intel Corporation
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the "Software"),
 * to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense,
 * and/or sell copies of the Software, and to permit persons to whom the
 * Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice (including the next
 * paragraph) shall be included in all copies or substantial portions of the
 * Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 *
 */

"""


def splice_rpn_expression(set, expression, symbols):
    tokens = expression.split()
    stack = []

    for token in tokens:
        stack.append(token)
        while stack and stack[-1] in exp_ops:
            op = stack.pop()
            argc, callback = exp_ops[op]
            args = []
            for i in range(0, argc):
                operand = stack.pop()
                if operand[0] == "$":
                    if operand in symbols:
                        operand = symbols[operand]
                    else:
                        raise Exception("Failed to resolve variable " + operand +
                                        " in expression " + expression + " for " + set['metricset'].get('name'));
                args.append(operand)

            subexp = callback(args)

            stack.append(subexp)

    if len(stack) != 1:
        raise Exception("Spurious empty rpn expression for " + set['metricset'].get('name') +
                        ".\nThis is probably due to some unhandled RPN operation, in the expression \"" +
                        expression + "\"")

    return stack.pop()


def output_b_counter_config(set, config_tuple):
    id, priority, config = config_tuple

    c("\nstatic const struct i915_oa_reg b_counter_config_" + set['perf_name_lc'] + "[] = {")

    c_indent(8)

    n_regs = 0
    for reg in config.findall("register"):
        if reg.get('type') == 'OA':
            addr = int(reg.get('address'), 16)
            addr_str = "0x%x" % addr
            val = int(reg.get('value'), 16)
            val_str = "0x%08x" % val

            c("{ _MMIO(" + addr_str + "), " + val_str + " },")
            n_regs = n_regs + 1

    c_outdent(8)

    c("};")


def output_flex_config(set, config_tuple):
    id, priority, config = config_tuple

    c("\nstatic const struct i915_oa_reg flex_eu_config_" + set['perf_name_lc'] + "[] = {")

    c_indent(8)

    n_regs = 0
    for reg in config.findall("register"):
        if reg.get('type') == 'FLEX':
            addr = int(reg.get('address'), 16)
            addr_str = "0x%x" % addr
            val = int(reg.get('value'), 16)
            val_str = "0x%08x" % val

            c("{ _MMIO(" + addr_str + "), " + val_str + " },")
            n_regs = n_regs + 1

    c_outdent(8)

    c("};")


def exp_to_symbol(exp):
    exp = exp.replace(' & ', '_')
    exp = exp.replace(' && ', '_and_')
    exp = exp.replace(' >= ', '_gte_')
    exp = exp.replace(' < ', '_lt_')
    exp = exp.replace(' ', '_')
    exp = exp.replace('(', '')
    exp = exp.replace(')', '')
    exp = exp.replace(')', '')

    return exp


def count_config_mux_registers(config):
    n_regs = 0
    for reg in config.findall("register"):
        if reg.get('type') == 'NOA':
            addr = reg.get('address')
            n_regs = n_regs + 1
    return n_regs


def output_mux_configs(set, config_tuples):

    for config_tuple in config_tuples:
        id, priority, config = config_tuple

        availability = config.get('availability')

        if availability:
            mnemonic_exp = splice_rpn_expression(set, availability, mnemonic_syms)
            mnemonic_exp = exp_to_symbol(mnemonic_exp)
            infix = "_" + str(id) + "_" + str(priority) + "_" + mnemonic_exp
        else:
            infix = ""

        c("\nstatic const struct i915_oa_reg mux_config_" + set['perf_name_lc'] + infix + "[] = {")

        c_indent(8)
        for reg in config.findall("register"):
            if reg.get('type') == 'NOA':
                addr = int(reg.get('address'), 16)
                addr_str = "0x%x" % addr
                val = int(reg.get('value'), 16)
                val_str = "0x%08x" % val

                c("{ _MMIO(" + addr_str + "), " + val_str + " },")
        c_outdent(8)

        c("};")


def output_mux_config_get_func(set, mux_config_tuples):
    c("\n")
    c("static const struct i915_oa_reg *")
    fname = "get_" + set['perf_name_lc']  + "_mux_config"
    c(fname + "(struct drm_i915_private *dev_priv,")
    c_indent(len(fname) + 1)
    c("int *len)")
    c_outdent(len(fname) + 1)
    c("{")
    c_indent(8)

    needs_close_if_block = 0
    i = 0
    for config_tuple in mux_config_tuples:
        id, priority, config = config_tuple

        availability = config.get('availability')

        if availability:
            needs_close_if_block = 1
            code_exp = splice_rpn_expression(set, availability, c_syms)
            mnemonic_exp = splice_rpn_expression(set, availability, mnemonic_syms)
            mnemonic_exp = exp_to_symbol(mnemonic_exp)
            infix = "_" + str(id) + "_" + str(priority) + "_" + mnemonic_exp

            if i > 0:
                else_prefix = "} else "
                subexp_indent = 11
            else:
                else_prefix = ""
                subexp_indent = 4

            lines = code_exp.split(' && ')
            n_lines = len(lines)
            if n_lines == 1:
                c(else_prefix + "if (" + lines[0] + ") {")
            else:
                c(else_prefix + "if (" + lines[0] + " &&")
                c_indent(subexp_indent)
                for i in range(1, (n_lines - 1)):
                    print_err(lines[i] + " &&")
                c(lines[(n_lines - 1)] + ") {")
                c_outdent(subexp_indent)
            c_indent(8)

            array_name = "mux_config_" + set['perf_name_lc']  + infix
            c("*len = ARRAY_SIZE(" + array_name + ");")
            c("return " + array_name + ";")

            c_outdent(8)
        else:
            # Unconditonal MUX config
            array_name = "mux_config_" + set['perf_name_lc']
            c("*len = ARRAY_SIZE(" + array_name + ");")
            c("return " + array_name + ";")

        i = i + 1

    if needs_close_if_block:
        c("}")
        c("\n");
        c("*len = 0;");
        c("return NULL;");

    c_outdent(8)
    c("}")


def output_b_and_flex_configs_select(set, b_counter_config_tuple, flex_config_tuple):
    id, priority, config = b_counter_config_tuple
    c("\n")
    c("dev_priv->perf.oa.b_counter_regs =")
    c_indent(8)
    c("b_counter_config_" + set['perf_name_lc']  + ";")
    c_outdent(8)
    c("dev_priv->perf.oa.b_counter_regs_len =")
    c_indent(8)
    c("ARRAY_SIZE(b_counter_config_" + set['perf_name_lc']  + ");")
    c_outdent(8)

    if flex_config_tuple:
        id, priority, config = flex_config_tuple
        c("\n")
        c("dev_priv->perf.oa.flex_regs =")
        c_indent(8)
        c("flex_eu_config_" + set['perf_name_lc']  + ";")
        c_outdent(8)
        c("dev_priv->perf.oa.flex_regs_len =")
        c_indent(8)
        c("ARRAY_SIZE(flex_eu_config_" + set['perf_name_lc']  + ");")
        c_outdent(8)


def output_sysfs_code(sets):
    for set in sets:
        perf_name = set['perf_name']
        perf_name_lc = set['perf_name_lc']

        c("\n")
        c("static ssize_t")
        c("show_" + perf_name_lc + "_id(struct device *kdev, struct device_attribute *attr, char *buf)")
        c("{")
        c_indent(8)
        c("return sprintf(buf, \"%d\\n\", METRIC_SET_ID_" + perf_name + ");")
        c_outdent(8)
        c("}")

        c("\n")
        c("static struct device_attribute dev_attr_" + perf_name_lc + "_id = {")
        c_indent(8)
        c(".attr = { .name = \"id\", .mode = 0444 },")
        c(".show = show_" + perf_name_lc + "_id,")
        c(".store = NULL,")
        c_outdent(8)
        c("};")

        c("\n")
        c("static struct attribute *attrs_" + perf_name_lc + "[] = {")
        c_indent(8)
        c("&dev_attr_" + perf_name_lc + "_id.attr,")
        c("NULL,")
        c_outdent(8)
        c("};")

        c("\n")
        c("static struct attribute_group group_" + perf_name_lc + " = {")
        c_indent(8)
        c(".name = \"" + set['guid'] + "\",")
        c(".attrs =  attrs_" + perf_name_lc + ",")
        c_outdent(8)
        c("};")


    h("extern int i915_perf_register_sysfs_" + chipset.lower() + "(struct drm_i915_private *dev_priv);")
    h("\n")

    c("\n")
    c("int")
    c("i915_perf_register_sysfs_" + chipset.lower() + "(struct drm_i915_private *dev_priv)")
    c("{")
    c_indent(8)
    c("int mux_len;")
    c("int ret = 0;")
    c("\n")

    for set in sets:
        c("if (get_" + set['perf_name_lc'] + "_mux_config(dev_priv, &mux_len)) {")
        c_indent(8)
        c("ret = sysfs_create_group(dev_priv->perf.metrics_kobj, &group_" + set['perf_name_lc'] + ");")
        c("if (ret)")
        c_indent(8)
        c("goto error_" + set['perf_name_lc'] + ";")
        c_outdent(8)
        c_outdent(8)
        c("}")

    c("\n")
    c("return 0;")
    c("\n")

    c_outdent(8)
    prev_set = None
    rev_sets = sets[:]
    rev_sets.reverse()
    for i in range(0, len(rev_sets) - 1):
        set0 = rev_sets[i]
        set1 = rev_sets[i + 1]
        c("error_" + set0['perf_name_lc'] + ":")
        c_indent(8)
        c("if (get_" + set['perf_name_lc'] + "_mux_config(dev_priv, &mux_len))")
        c_indent(8)
        c("sysfs_remove_group(dev_priv->perf.metrics_kobj, &group_" + set1['perf_name_lc'] + ");")
        c_outdent(8)
        c_outdent(8)
    c("error_" + rev_sets[-1]['perf_name_lc'] + ":")
    c_indent(8)
    c("return ret;")
    c_outdent(8)

    c("}")

    h("extern void i915_perf_unregister_sysfs_" + chipset.lower() + "(struct drm_i915_private *dev_priv);")
    h("\n")

    c("\n")
    c("void")
    c("i915_perf_unregister_sysfs_" + chipset.lower() + "(struct drm_i915_private *dev_priv)")
    c("{")
    c_indent(8)
    c("int mux_len;")
    c("\n")
    for set in sets:
        c("if (get_" + set['perf_name_lc'] + "_mux_config(dev_priv, &mux_len))")
        c_indent(8)
        c("sysfs_remove_group(dev_priv->perf.metrics_kobj, &group_" + set['perf_name_lc'] + ");")
        c_outdent(8)
    c_outdent(8)
    c("}")

   
parser = argparse.ArgumentParser()
parser.add_argument("xml", nargs="+", help="XML description of metrics")
parser.add_argument("--guids", required=True, help="Metric set GUID registry")
parser.add_argument("--chipset", required=True, help="Chipset being output for")
parser.add_argument("--c-out", required=True, help="Filename for generated C code")
parser.add_argument("--h-out", required=True, help="Filename for generated header")
parser.add_argument("--sysfs", action="store_true", help="Output code for sysfs")
parser.add_argument("--whitelist", help="Override default metric set whitelist")
parser.add_argument("--no-whitelist", action="store_true", help="Bypass default metric set whitelist")
parser.add_argument("--blacklist", help="Don't generate anything for given metric sets")

args = parser.parse_args()

guids = {}

guids_xml = ET.parse(args.guids)
for guid in guids_xml.findall(".//guid"):
    guids[guid.get('config_hash')] = guid.get('id')

chipset = args.chipset.upper()

header_file = open(args.h_out, 'w')
c_file = open(args.c_out, 'w')

h(copyright)
h("#ifndef __I915_OA_" + chipset + "_H__\n")
h("#define __I915_OA_" + chipset + "_H__\n\n")

c(copyright)

if args.sysfs:
    c("#include <linux/sysfs.h>")
    c("\n")

c("#include \"i915_drv.h\"\n")
c("#include \"i915_oa_" + args.chipset + ".h\"\n")

sets = []

for arg in args.xml:
    xml = ET.parse(arg)

    for metricset in xml.findall(".//set"):

        assert metricset.get('chipset') == chipset

        set_name = metricset.get('symbol_name')

        if args.whitelist:
            set_whitelist = args.whitelist.split()
            if set_name not in set_whitelist:
                continue

        if args.blacklist:
            set_blacklist = args.blacklist.split()
        else:
            set_blacklist = default_set_blacklist
        if set_name in set_blacklist:
            continue

        configs = metricset.findall("register_config")
        if len(configs) == 0:
            print_err("WARNING: Missing register configuration for set \"" + metricset.get('name') + "\" (SKIPPING)")
            continue

        v2_hash = get_v2_config_hash(metricset)
        if v2_hash not in guids:
            print_err("WARNING: No GUID found for metric set " + chipset + ", " + metricset.get('name') + " (SKIPPING)")
            continue

        perf_name_lc = underscore(set_name)
        perf_name = perf_name_lc.upper()

        set = { 'name': set_name,
                'metricset': metricset,
                'chipset_lc': chipset.lower(),
                'perf_name_lc': perf_name_lc,
                'perf_name': perf_name,
                'guid': guids[v2_hash],
                'configs': configs
              }
        sets.append(set)

    c("\nenum metric_set_id {")
    c_indent(8)
    c("METRIC_SET_ID_" + sets[0]['perf_name'] + " = 1,");
    for set in sets[1:]:
        c("METRIC_SET_ID_" + set['perf_name'] + ",");

    c_outdent(8)
    c("};")

    h("extern int i915_oa_n_builtin_metric_sets_" + chipset.lower() + ";\n\n")
    c("\nint i915_oa_n_builtin_metric_sets_" + chipset.lower() + " = " + str(len(sets)) + ";\n")

    for set in sets:

        set_name = set['name']

        configs = set['configs']

        mux_configs = []
        b_counter_configs = []
        flex_configs = []
        for config in configs:

            config_id = int(config.get('id'))
            if config.get('priority'):
                config_priority = int(config.get('priority'))
            else:
                config_priority = 0

            is_mux_config = False
            is_b_counter_config = False
            is_flex_config = False

            for reg in config.findall("register"):
                reg_type = reg.get('type')
                if reg_type == 'NOA':
                    if is_mux_config == False:
                        mux_configs.append((config_id, config_priority, config))
                        is_mux_config = True
                elif reg_type == 'OA':
                    if is_b_counter_config == False:
                        assert config.get('availability') == None
                        b_counter_configs.append((config_id, config_priority, config))
                        is_b_counter_config = True
                elif reg_type == 'FLEX':
                    if is_flex_config == False:
                        assert chipset != 'HSW'
                        assert config.get('availability') == None
                        flex_configs.append((config_id, config_priority, config))
                        is_flex_config = True

        assert len(mux_configs) >= 1

        if len(b_counter_configs) == 0:
            empty = ET.Element('register_config')
            b_counter_configs.append((0, 0, empty))

        assert len(b_counter_configs) == 1

        output_b_counter_config(set, b_counter_configs[0])


        assert len(flex_configs) == 0 or len(flex_configs) == 1

        flex_config = None
        if len(flex_configs) == 1:
            flex_config = flex_configs[0]
            output_flex_config(set, flex_config)

        mux_configs.sort(key=itemgetter(0, 1))
        output_mux_configs(set, mux_configs)

        output_mux_config_get_func(set, mux_configs)


h("extern int i915_oa_select_metric_set_" + chipset.lower() + "(struct drm_i915_private *dev_priv);")
h("\n")

c("\n")
c("int i915_oa_select_metric_set_" + chipset.lower() + "(struct drm_i915_private *dev_priv)")
c("{")
c_indent(8)

c("dev_priv->perf.oa.mux_regs = NULL;")
c("dev_priv->perf.oa.mux_regs_len = 0;")
c("dev_priv->perf.oa.b_counter_regs = NULL;")
c("dev_priv->perf.oa.b_counter_regs_len = 0;")
if chipset != "HSW":
    c("dev_priv->perf.oa.flex_regs = NULL;")
    c("dev_priv->perf.oa.flex_regs_len = 0;")
c("\n")

c("switch (dev_priv->perf.oa.metrics_set) {")

for set in sets:
    perf_name = set['perf_name']
    perf_name_lc = set['perf_name_lc']

    c("case METRIC_SET_ID_" + perf_name + ":")
    c_indent(8)
    c("dev_priv->perf.oa.mux_regs =")
    c_indent(8)
    fname = "get_" + perf_name_lc + "_mux_config"
    c(fname + "(dev_priv,")
    c_indent(len(fname) + 1)
    c("&dev_priv->perf.oa.mux_regs_len);")
    c_outdent(len(fname) + 1)
    c_outdent(8)
    c("if (!dev_priv->perf.oa.mux_regs) {")
    c_indent(8)
    c("DRM_DEBUG_DRIVER(\"No suitable MUX config for \\\"" + set['perf_name'] + "\\\" metric set\");")
    c("\n")
    c("/* EINVAL because *_register_sysfs already checked this")
    c(" * and so it wouldn't have been advertised so userspace and")
    c(" * so shouldn't have been requested")
    c(" */")
    c("return -EINVAL;")
    c_outdent(8)
    c("}")

    c("")
    output_b_and_flex_configs_select(set, b_counter_configs[0], flex_config)
    c("\n")
    c("return 0;")
    c_outdent(8)

c("default:")
c_indent(8)
c("return -ENODEV;")
c_outdent(8)

c("}")
c_outdent(8)
c("}")

if args.sysfs:
    output_sysfs_code(sets)

h("#endif\n")

