import os

# 模板文件所在的目录，这里假设是ai_image_app/templates
template_dir = 'ai_image_app/templates'

# 遍历模板目录下的所有文件
for root, dirs, files in os.walk(template_dir):
    for file in files:
        file_path = os.path.join(root, file)
        # 只处理HTML文件
        if file.endswith('.html'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            # 进行替换
            content = content.replace("url_for('static', filename='", "{% static '")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)