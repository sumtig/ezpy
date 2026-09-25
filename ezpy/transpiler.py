import re
import sys
import os
from datetime import datetime

def translate_single_line(line):
    match_indent = re.match(r'^(\s*)', line)
    indent = match_indent.group(1) if match_indent else ""
    stripped = line.strip()

    # 1. ask prompt -> var
    ask_m = re.match(r'^ask\s+(.+?)\s*->\s*(\w+)$', stripped)
    if ask_m:
        return f"{indent}{ask_m.group(2)} = input({ask_m.group(1)})"

    # 2. input("...", var)
    in_assign_m = re.match(r'^input\s*\(\s*(.+?)\s*,\s*(\w+)\s*\)$', stripped)
    if in_assign_m:
        return f"{indent}{in_assign_m.group(2)} = input({in_assign_m.group(1)})"

    # 3. input("..."), output to var
    in_out_m = re.match(r'^input\s*\((.+?)\)\s*(?:,\s*)?output\s+to\s+["\']?(\w+)["\']?$', stripped)
    if in_out_m:
        return f"{indent}{in_out_m.group(2)} = input({in_out_m.group(1)})"

    # 4. printf(...)
    printf_m = re.match(r'^printf\s*\((.+)\)$', stripped)
    if printf_m:
        return f"{indent}print(f{printf_m.group(1)})"

    return line

def translate_code(source_code):
    source_code = source_code.replace("\xa0", " ")
    lines = source_code.splitlines()
    new_lines = []

    fail_pattern = re.compile(r'^(\s*)if\s+(.+?)\s+fails\s*:\s*$')
    isnt_pattern = re.compile(r'^(\s*)if\s+(.+?)\s+isnt\s+(.+?)\s*:\s*$')
    repeat_pattern = re.compile(r'^(\s*)repeat\s+(.+?)\s+times\s*:\s*$')
    repeat_while_pattern = re.compile(r'^(\s*)repeat\s+while\s+(.+?)\s*:\s*$')
    generic_block_pattern = re.compile(r'^(\s*)(if\b|elif\b|else\b|for\b|while\b|def\b|class\b).*:\s*$')

    i = 0
    while i < len(lines):
        line = lines[i]
        fail_match = fail_pattern.match(line)
        isnt_match = isnt_pattern.match(line)
        repeat_match = repeat_pattern.match(line)
        repeat_while_match = repeat_while_pattern.match(line)
        generic_block_match = generic_block_pattern.match(line)

        if fail_match:
            indent = fail_match.group(1)
            expression = fail_match.group(2)

            body_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].replace("\xa0", " ")
                if next_line.startswith("    ") or next_line.startswith("\t") or next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                else:
                    break

            if "print(" in expression or "printf(" in expression:
                if "printf(" in expression:
                    expression = re.sub(r'printf\((.+)\)', r'print(f\1)', expression)

                print_arg_match = re.search(r'print\((.+)\)', expression)
                expected_eval = print_arg_match.group(1) if print_arg_match else '""'

                new_lines.append(f"{indent}import sys, io")
                new_lines.append(f"{indent}_ez_buffer = io.StringIO()")
                new_lines.append(f"{indent}_ez_old_stdout = sys.stdout")
                new_lines.append(f"{indent}try:")
                new_lines.append(f"{indent}    sys.stdout = _ez_buffer")
                new_lines.append(f"{indent}    {expression}")
                new_lines.append(f"{indent}    sys.stdout = _ez_old_stdout")
                new_lines.append(f"{indent}    _ez_output = _ez_buffer.getvalue()")
                new_lines.append(f"{indent}    _ez_expected = str({expected_eval}) + '\\n'")
                new_lines.append(f"{indent}    if _ez_output != _ez_expected:")
                new_lines.append(f"{indent}        raise RuntimeError('Print output mismatch')")
                new_lines.append(f"{indent}    print(_ez_output, end='')")
                new_lines.append(f"{indent}except Exception:")
                new_lines.append(f"{indent}    sys.stdout = _ez_old_stdout")

                if body_lines:
                    cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                    translated_sub = translate_code("\n".join(cleaned_body))
                    for sub_line in translated_sub.splitlines():
                        new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
                else:
                    new_lines.append(f"{indent}    pass")
            else:
                new_lines.append(f"{indent}try:")
                new_lines.append(f"{indent}    {expression}")
                new_lines.append(f"{indent}except Exception:")

                if body_lines:
                    cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                    translated_sub = translate_code("\n".join(cleaned_body))
                    for sub_line in translated_sub.splitlines():
                        new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
                else:
                    new_lines.append(f"{indent}    pass")

            i = j

        elif isnt_match:
            indent = isnt_match.group(1)
            left_expr = isnt_match.group(2)
            right_expr = isnt_match.group(3)

            body_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].replace("\xa0", " ")
                if next_line.startswith("    ") or next_line.startswith("\t") or next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                else:
                    break

            if "print(" in left_expr or "print(" in right_expr or "printf(" in left_expr or "printf(" in right_expr:
                if "printf(" in left_expr: left_expr = re.sub(r'printf\((.+)\)', r'print(f\1)', left_expr)
                if "printf(" in right_expr: right_expr = re.sub(r'printf\((.+)\)', r'print(f\1)', right_expr)

                new_lines.append(f"{indent}import sys, io")
                new_lines.append(f"{indent}_ez_buf1 = io.StringIO()")
                new_lines.append(f"{indent}_ez_buf2 = io.StringIO()")
                new_lines.append(f"{indent}_ez_old_stdout = sys.stdout")
                new_lines.append(f"{indent}try:")
                new_lines.append(f"{indent}    sys.stdout = _ez_buf1")
                new_lines.append(f"{indent}    {left_expr}")
                new_lines.append(f"{indent}    sys.stdout = _ez_buf2")
                new_lines.append(f"{indent}    {right_expr}")
                new_lines.append(f"{indent}    sys.stdout = _ez_old_stdout")
                new_lines.append(f"{indent}    if _ez_buf1.getvalue() != _ez_buf2.getvalue():")
                new_lines.append(f"{indent}        _ez_isnt_matched = True")
                new_lines.append(f"{indent}    else:")
                new_lines.append(f"{indent}        _ez_isnt_matched = False")
                new_lines.append(f"{indent}        print(_ez_buf1.getvalue(), end='')")
                new_lines.append(f"{indent}except Exception:")
                new_lines.append(f"{indent}    sys.stdout = _ez_old_stdout")
                new_lines.append(f"{indent}    _ez_isnt_matched = True")
                new_lines.append(f"{indent}if _ez_isnt_matched:")
            else:
                new_lines.append(f"{indent}if {left_expr} != {right_expr}:")

            if body_lines:
                cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                translated_sub = translate_code("\n".join(cleaned_body))
                for sub_line in translated_sub.splitlines():
                    new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
            else:
                new_lines.append(f"{indent}    pass")

            i = j

        elif repeat_match:
            indent = repeat_match.group(1)
            count_expr = repeat_match.group(2)

            body_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].replace("\xa0", " ")
                if next_line.startswith("    ") or next_line.startswith("\t") or next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                else:
                    break

            new_lines.append(f"{indent}for _ in range({count_expr}):")

            if body_lines:
                cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                translated_sub = translate_code("\n".join(cleaned_body))
                for sub_line in translated_sub.splitlines():
                    new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
            else:
                new_lines.append(f"{indent}    pass")

            i = j

        elif repeat_while_match:
            indent = repeat_while_match.group(1)
            condition = repeat_while_match.group(2)

            body_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].replace("\xa0", " ")
                if next_line.startswith("    ") or next_line.startswith("\t") or next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                else:
                    break

            new_lines.append(f"{indent}while {condition}:")

            if body_lines:
                cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                translated_sub = translate_code("\n".join(cleaned_body))
                for sub_line in translated_sub.splitlines():
                    new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
            else:
                new_lines.append(f"{indent}    pass")

            i = j

        elif generic_block_match:
            indent = generic_block_match.group(1)
            header_line = line.strip()

            body_lines = []
            j = i + 1
            while j < len(lines):
                next_line = lines[j].replace("\xa0", " ")
                if next_line.startswith("    ") or next_line.startswith("\t") or next_line.strip() == "":
                    body_lines.append(next_line)
                    j += 1
                else:
                    break

            new_lines.append(f"{indent}{header_line}")

            if body_lines:
                cleaned_body = [bl[4:] if bl.startswith("    ") else bl for bl in body_lines]
                translated_sub = translate_code("\n".join(cleaned_body))
                for sub_line in translated_sub.splitlines():
                    new_lines.append(f"{indent}    {sub_line}" if sub_line.strip() else "")
            else:
                new_lines.append(f"{indent}    pass")

            i = j

        else:
            new_lines.append(translate_single_line(line))
            i += 1

    return "\n".join(new_lines)

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m ezpy.transpiler <filename.ezpy>")
        return

    filename = sys.argv[1]
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        return

    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = [
        f"# This script was translated using ezpy on {timestamp}.",
        "# Do not edit this file directly; edit your .ezpy source file instead.",
        ""
    ]

    translated_body = translate_code(content)
    translated_content = "\n".join(header) + translated_body

    base_name = os.path.splitext(filename)[0]
    output_filename = base_name + ".py"

    with open(output_filename, "w", encoding="utf-8") as f:
        f.write(translated_content)

    print(f"Successfully compiled '{filename}' into pristine Python -> '{output_filename}'!")

if __name__ == "__main__":
    main()
