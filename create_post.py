import datetime
import dateutil.tz
import jinja2
import os
import sys

DEFAULT_POSTS_PATH = './_posts'
POST_TEMPLATE = 'post.template'

def get_title():
    try:
        return sys.argv[1]
    except IndexError:
        raise RuntimeError("You need to add the title as a parameter")

def format_title(title):
    return title.lower().replace(" ", "-")

def get_file_path(formatted_title):
    today = str(datetime.date.today())
    return os.path.join(DEFAULT_POSTS_PATH,
                        today + '-' + formatted_title + ".markdown")

def get_current_day():
    local_tz = dateutil.tz.tzlocal()
    current_day = datetime.datetime.now(local_tz)
    return str(current_day.date()) + current_day.strftime(" %X %z")

def get_rendered_content(title):
    path = os.path.dirname(os.path.abspath(__file__))
    template_environment = jinja2.Environment(
        autoescape=False,
        loader=jinja2.FileSystemLoader(os.path.join(path, 'templates')),
        trim_blocks=False)
    context = {
        'title': title,
        'current_day': get_current_day(),
        'categories': "tripleo openstack"
    }
    return template_environment.get_template(POST_TEMPLATE).render(context)

def write_post(content, file_path):
    with open(file_path, 'w+') as post:
        post.write(content)

if __name__ == '__main__':
    title = get_title()
    file_path = get_file_path(format_title(title))
    content = get_rendered_content(title)
    write_post(content, file_path)
    print(file_path)
