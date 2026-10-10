import glob
import jinja2

env = jinja2.Environment()
for f in glob.glob("app/templates/**/*.html", recursive=True):
    try:
        env.parse(open(f, encoding="utf-8").read())
    except jinja2.TemplateSyntaxError as e:
        print("ERRO", f, "linha", e.lineno, e.message)
print("conferido")