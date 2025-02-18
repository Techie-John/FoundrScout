from django.shortcuts import render, HttpResponse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import praw
from groq import Groq
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

def home(request):
    return HttpResponse("Home Page")

@csrf_exempt
def dashboard(request):
    if request.method == 'POST':
        try:
            subreddit_name = request.POST.get('subreddit', 'startups')
            post_limit = int(request.POST.get('limit', 5))
            
            reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_SECRET'),
                user_agent='IDEATOR/1.0'
            )
            
            subreddit = reddit.subreddit(subreddit_name)
            posts = subreddit.top('day', limit=post_limit)
            
            client = Groq(api_key=os.getenv('GROQ_KEY'))
            analyzed_posts = []
            
            for post in posts:
                response = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"Identify business opportunities in this Reddit post (respond in markdown bullets):\n\nTitle: {post.title}\nContent: {post.selftext[:500]}\nSubreddit: {subreddit_name}"
                    }],
                    model="mixtral-8x7b-32768",
                    temperature=0.5
                )
                
                analyzed_posts.append({
                    'title': post.title,
                    'url': f'https://reddit.com{post.permalink}',
                    'score': post.score,
                    'analysis': response.choices[0].message.content
                })
            
            return JsonResponse({
                'status': 'success',
                'subreddit': subreddit_name,
                'results': analyzed_posts
            })
            
        except Exception as e:
            logger.error(f"Analysis error: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': f"Failed to analyze: {str(e)}"
            }, status=500)
    
    return render(request, 'dashboard.html')

# API endpoint for React frontend
@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def analyze_api(request):
    if request.method == 'OPTIONS':
        response = JsonResponse({})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response

    if request.method == 'POST':
        try:
            data = request.POST
            subreddit = data.get('subreddit', 'seo').strip()
            limit = min(int(data.get('limit', 20)), 20)  # Max 20 posts

            # Log the subreddit being queried
            logger.info(f"Analyzing subreddit: {subreddit}")

            # Initialize Reddit API
            reddit = praw.Reddit(
                client_id=os.getenv('REDDIT_CLIENT_ID'),
                client_secret=os.getenv('REDDIT_SECRET'),
                user_agent=f'IDEATOR/1.0 (Subreddit: {subreddit})'
            )

            # Validate subreddit existence
            try:
                subreddit_instance = reddit.subreddit(subreddit)
                subreddit_instance.id  # Raises exception if subreddit doesn't exist
            except praw.exceptions.PRAWException as e:
                logger.error(f"Subreddit error: {str(e)}")
                return JsonResponse({'error': f'Subreddit "{subreddit}" not found or inaccessible'}, status=404)

            # Fetch posts
            posts = list(subreddit_instance.top('day', limit=limit))  # Convert to list to debug
            logger.info(f"Fetched {len(posts)} posts from r/{subreddit}")

            if not posts:
                return JsonResponse({'error': f'No posts found in r/{subreddit}'}, status=404)

            # Analyze posts with Groq
            client = Groq(api_key=os.getenv('GROQ_KEY'))
            results = []

            for post in posts:
                response = client.chat.completions.create(
                    messages=[{
                        "role": "user",
                        "content": f"Analyze this Reddit post for startup opportunities, meaning: generate startup ideas from this post (format as markdown):\nTitle: {post.title}\nContent: {post.selftext[:300]}\nSubreddit: {subreddit}"
                    }],
                    model="mixtral-8x7b-32768"
                )

                results.append({
                    'id': post.id,
                    'title': post.title,
                    'url': f'https://reddit.com{post.permalink}',
                    'upvotes': post.score,
                    'analysis': response.choices[0].message.content
                })

            response = JsonResponse({'data': results})
            response["Access-Control-Allow-Origin"] = "*"
            return response

        except praw.exceptions.PRAWException as e:
            logger.error(f"Reddit API error: {str(e)}")
            return JsonResponse({'error': f'Reddit API error: {str(e)}'}, status=400)
        except Exception as e:
            logger.error(f"Internal server error: {str(e)}")
            return JsonResponse({'error': 'Internal server error'}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)