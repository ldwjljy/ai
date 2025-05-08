# ai_image_app/views.py

import os
import time
import re
import logging
import dashscope
from dashscope import Generation
import threading
import requests
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from werkzeug.utils import secure_filename
from urllib.parse import urlparse

# 配置DashScope API密钥
dashscope.api_key = 'sk-ae27866e71264f8088f5a4489c93ddfb'

# 模型兼容配置
MODEL_COMPATIBILITY = {
    'wpm2.1-t3k.info': {
        'new_name': 'wanx2.1-t2i-turbo',
        'sizes': ['1024x1024', '1280x720'],
        'size_mapping': {
            '1024x1024': '1024x1024',
            '1280x720': '1280x720',
            '720x1280': '720x1280'  # 虽然前端不支持但仍保留映射
        },
        'domain_pattern': r'^https?://dashscope\.aliyuncs\.com/.*'  # 实际域名正则
    },
    'ImageSynthesisModels.wmrc_v1': {
        'new_name': 'wanx2.1-t2i-pro',
        'sizes': ['1024x1024', '720x1280'],
        'size_mapping': {
            '1024x1024': '1024x1024',
            '1280x720': '1280x720',
            '720x1280': '720x1280'
        },
        'domain_pattern': r'^https?://dashscope\.aliyuncs\.com/.*'
    }
}

os.environ['NO_PROXY'] = 'dashscope.aliyuncs.com'

logger = logging.getLogger(__name__)

def index(request):
    return render(request, 'index.html')

def creation(request):
    return render(request, 'creation.html')

def agreement(request):
    return render(request, 'agreement.html')

def profile(request):
    return render(request, 'profile.html')

def login(request):
    return render(request, 'login.html')

def signup(request):
    return render(request, 'signup.html')

@csrf_exempt
def generate_image(request):
    if request.method == 'POST':
        try:
            data = request.POST.dict()

            # 打印请求参数
            logger.info(f"请求参数: {data}")

            # 严格参数校验
            required_params = ['prompt', 'size', 'model']
            for param in required_params:
                if param not in data:
                    logger.error(f"Missing required parameter: {param}")
                    return JsonResponse({'error': f'缺少必要参数: {param}'}, status=400)

            cleaned_prompt = clean_prompt(data['prompt'].strip())
            raw_model = data['model']
            raw_size = data['size']

            # 模型兼容处理
            if raw_model in MODEL_COMPATIBILITY:
                compat = MODEL_COMPATIBILITY[raw_model]
                model = compat['new_name']
                size = compat['size_mapping'].get(raw_size, raw_size)  # 使用映射表
            else:
                return JsonResponse({'error': '不支持的模型'}, status=400)

            # 尺寸验证
            if size not in compat['sizes']:
                return JsonResponse({'error': f'模型不支持该尺寸: {size}'}, status=400)

            # 调用阿里云生成接口
            result = Generation.call(
                model=model,
                prompt=cleaned_prompt,
                size=size,
                n=1,
                async_mode=True,
                parameters={'enable_async': True}
            )

            logger.info(f"API返回结果: {result}")

            if result.status_code == 200:
                return JsonResponse({'task_id': result.output['task_id']})
            else:
                logger.error(f"API错误: {result.message}, code: {result.code}")
                return JsonResponse({
                    'error': f'API错误：{result.message}',
                    'code': result.code
                }, status=result.status_code)

        except Exception as e:
            logger.error(f"服务端异常: {str(e)}", exc_info=True)
            return JsonResponse({'error': '服务器内部错误'}, status=500)

def check_status(request):
    try:
        task_id = request.GET.get('task_id')
        result = Generation.get_result(task_id=task_id)

        # 打印返回结果
        logger.info(f"返回结果: {result}")

        if result.status_code != 200:
            return JsonResponse({
                'status': 'failed',
                'error': result.message
            }, status=500)

        task_status = result.output['task_status']

        if task_status == 'SUCCEEDED':
            image_url = result.output['results'][0]['url']

            # 打印返回的URL
            logger.info(f"返回的URL: {image_url}")

            # 严格验证URL格式
            model = result.parameters.get('model', 'wanx2.1-t2i-turbo')
            if not re.match(MODEL_COMPATIBILITY[model]['domain_pattern'], image_url):
                logger.error(f"非法URL格式: {image_url}")
                return JsonResponse({
                    'status': 'failed',
                    'error': '无效的图片地址格式'
                }, status=500)

            # 增强下载逻辑
            filename = secure_filename(f"{task_id}.png").replace('%', '_').replace('/', '_').replace(':', '_').replace('\\', '_')
            filepath = os.path.join(settings.MEDIA_ROOT, filename)

            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(max_retries=3)
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            try:
                response = session.get(image_url, timeout=15)
                response.raise_for_status()

                if 'image/' not in response.headers.get('Content-Type', ''):
                    raise ValueError("非图片类型响应")

                with open(filepath, 'wb') as f:
                    f.write(response.content)

                return JsonResponse({
                    'status': 'succeeded',
                    'url': f'{settings.MEDIA_URL}{filename}'
                })
            except Exception as e:
                logger.error(f"图片下载失败: {str(e)}")
                return JsonResponse({
                    'status': 'failed',
                    'error': '图片下载失败'
                }, status=500)

        elif task_status == 'FAILED':
            return JsonResponse({
                'status': 'failed',
                'error': result.output['message']
            }, status=500)

        return JsonResponse({'status': 'processing'})

    except Exception as e:
        logger.error(f"状态检查失败: {str(e)}")
        return JsonResponse({
            'status': 'failed',
            'error': '状态查询失败'
        }, status=500)

# 清理旧文件的函数
def cleanup_old_files():
    while True:
        try:
            now = time.time()
            for root, dirs, files in os.walk(settings.MEDIA_ROOT):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.stat(file_path).st_mtime < now - 7 * 86400:
                        os.remove(file_path)
            time.sleep(86400)
        except Exception as e:
            logger.error(f"文件清理失败: {str(e)}")
            time.sleep(3600)  # 失败后等待1小时再重试

def validate_model_config():
    """启动时验证配置完整性"""
    required_keys = ['new_name', 'sizes', 'domain_pattern']
    for model_name, config in MODEL_COMPATIBILITY.items():
        # 检查必要键
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Invalid config for {model_name}: missing '{key}'")

def clean_prompt(prompt):
    # 使用正向否定预查精确匹配非dashscope域名
    cleaned = re.sub(
        r'https?://(?!dashscope\.aliyuncs\.com)[^\s]+',
        '',
        prompt,
        flags=re.IGNORECASE
    )
    return cleaned.strip()

# 启动清理线程
cleanup_thread = threading.Thread(target=cleanup_old_files)
cleanup_thread.daemon = True
cleanup_thread.start()

# 验证模型配置
validate_model_config()
# Create your views here.
