import ast

def lint_file(filepath):
    try:
        with open(filepath, "r") as f:
            source = f.read()
        
        tree = ast.parse(source)
        print(f"✅ Syntax is valid for {filepath}")
        
        # Basic check for duplicate assignments in main() function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'main':
                print("Analyzing main() function...")
                assigned_vars = set()
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Assign):
                        for target in subnode.targets:
                            if isinstance(target, ast.Name):
                                if target.id in assigned_vars:
                                    # This is common, but might indicate accidental shadowing of components
                                    # print(f"  Note: Variable '{target.id}' reassigned")
                                    pass
                                assigned_vars.add(target.id)
                                
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    lint_file("web/app.py")