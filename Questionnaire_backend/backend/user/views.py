from django.shortcuts import render
from django.http import JsonResponse

# Create your views here.
from .models import User,Survey
from .models import BaseQuestion,BlankQuestion,ChoiceQuestion,ChoiceOption,RatingQuestion
from .models import Answer,BlankAnswer,ChoiceAnswer,RatingAnswer
from .models import Submission,SurveyStatistic,Template,RewardOffering,UserRewardRecord   

import json
from django.core.mail import BadHeaderError, send_mail
from django.http import HttpResponse, HttpResponseRedirect

from django.core.mail import EmailMessage

from itsdangerous import URLSafeTimedSerializer as utsr
import base64
from django.conf import settings as django_settings
from django.utils import timezone
from django.db import transaction 

from rest_framework.views import APIView
import itertools

from itertools import chain  
from operator import attrgetter 

serveAddress="http:127.0.0.1:8080"

#普通问卷的展示界面：
def display_answer_normal(request,username,questionnaireId,submissionId):
    user=User.objects.get(username=username)
    if user is None:
        return HttpResponse(content='User not found', status=404) 
        
    survey=Survey.objects.get(SurveyID=questionnaireId)
    if survey is None:
        return HttpResponse(content='Questionnaire not found', status=404)   
    
    submission=Submission.objects.get(SubmissionID=submissionId)
    if submission is None:
        return HttpResponse(content='Submission not found', status=404)  
    
    all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionID','QuestionNumber').all())
                                                    
    # 将迭代器转换为列表 (按QuestionNumber递增排序)
    all_questions_list = list(all_questionList_iterator)
    all_questions_list.sort(key=lambda x: x['QuestionNumber']) 

    #print(all_questions_list.length())
    questionList=[]
    #print(all_questions)
    for question in all_questions_list:
        if question["Category"]==1 or question["Category"]==2:    #选择题

            #该单选题的用户选项:当前问卷当前submission(如果用户未选，则找不到对应的答案记录)
            if question["Category"]==1:
                optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])  #只有一条记录
                
                #用户未填该单选题
                if not optionAnswer_query.exists():
                    answer=-1
                #用户填了这个单选题，有一条答案记录
                else:
                    answer=optionAnswer_query.first().ChoiceOptions.OptionID
            
            #该多选题的用户选项:当前问卷当前submission
            else:
                optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])#一或多条记录
                #用户未填该多选题
                if not optionAnswer_query.exists():answer=[]
                #用户填了这个多选题，有一条/多条答案记录
                else:
                    answer=[]
                    for optionAnswer in optionAnswer_query:
                        answer.append(optionAnswer.ChoiceOptions.OptionID)

            optionList=[]
            #所有选项
            options_query=ChoiceOption.objects.filter(Question=question["QuestionID"])
            for option in options_query:
                optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,'optionId':option.OptionID})
            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                    'optionList':optionList,'Answer':answer})
            
        elif question["Category"]==3:                  #填空题
            #该填空题的用户答案:有且仅有一条记录
            blankAnswer_query=BlankAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
            #用户未填该填空题
            if not blankAnswer_query.exists():
                answer=""
            else:
                answer=blankAnswer_query.first().Content
            
            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],
                                    'correctAnswer':question["CorrectAnswer"],'Answer':answer})

        elif question["Category"]==4:                  #评分题
            #该评分题的用户答案:有且仅有一条记录
            ratingAnswer_query=RatingAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
            #用户未填该评分题
            if not ratingAnswer_query.exists():
                answer=0
            else:
                #print("123")
                answer=ratingAnswer_query.first().Rate

            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],'Answer':answer})

    data={'Title':survey.Title,'description':survey.Description,'questionList':questionList}
    return JsonResponse(data)


#考试问卷的展示界面：
def display_answer_test(request,username,questionnaireId,submissionId):
    print("start display_answer_test")
    # print(submissionId)
    user=User.objects.get(username=username)
    if user is None:
        return HttpResponse(content='User not found', status=404) 
        
    survey=Survey.objects.get(SurveyID=questionnaireId)
    if survey is None:
        return HttpResponse(content='Questionnaire not found', status=404)   
    
    submission=Submission.objects.get(SubmissionID=submissionId)
    if submission is None:
        return HttpResponse(content='Submission not found', status=404)  
    score=submission.Score
    
    all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionID','QuestionNumber').all())
    
    # 将迭代器转换为列表 (按QuestionNumber递增排序)
    all_questions_list = list(all_questionList_iterator)
    all_questions_list.sort(key=lambda x: x['QuestionNumber']) 

    questionList=[]
    #print(all_questions)
    for question in all_questions_list:
        if question["Category"]==1 or question["Category"]==2:    #选择题

            #该单选题的用户选项:当前问卷当前submission(如果用户未选，则找不到对应的答案记录)
            if question["Category"]==1:
                optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])  #只有一条记录
                
                #用户未填该单选题
                if not optionAnswer_query.exists():
                    answer=-1
                #用户填了这个单选题，有一条答案记录
                else:
                    answer=optionAnswer_query.first().ChoiceOptions.OptionID
            
            #该多选题的用户选项:当前问卷当前submission
            else:
                optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])#一或多条记录
                #用户未填该多选题
                if not optionAnswer_query.exists():answer=[]
                #用户填了这个多选题，有一条/多条答案记录
                else:
                    answer=[]
                    for optionAnswer in optionAnswer_query:
                        answer.append(optionAnswer.ChoiceOptions.OptionID)

            optionList=[]
            #所有选项
            options_query=ChoiceOption.objects.filter(Question=question["QuestionID"])
            for option in options_query:
                optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,'optionId':option.OptionID})
            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                    'optionList':optionList,'Answer':answer})
            
        elif question["Category"]==3:                  #填空题
            #该填空题的用户答案:有且仅有一条记录
            blankAnswer_query=BlankAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
            #用户未填该填空题
            if not blankAnswer_query.exists():
                answer=""
            else:
                answer=blankAnswer_query.first().Content
            
            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],
                                    'correctAnswer':question["CorrectAnswer"],'Answer':answer})

        elif question["Category"]==4:                  #评分题
            #该评分题的用户答案:有且仅有一条记录
            ratingAnswer_query=RatingAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
            #用户未填该评分题
            if not ratingAnswer_query.exists():
                answer=0
            else:
                answer=ratingAnswer_query.first().Rate

            questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                    'isNecessary':question["IsRequired"],'score':question["Score"],'Answer':answer})


    data={'Title':survey.Title,'description':survey.Description,'questionList':questionList,'score':score}
    # print(questionList[0])
    return JsonResponse(data)




#问卷填写界面：向前端传输问卷当前暂存的填写记录
class GetStoreFillView(APIView):
    def get(self, request, *args, **kwargs):  
        # 从查询参数中获取userName和surveyID   
        userName = kwargs.get('userName')  
        surveyID = kwargs.get('surveyID')   
        submissionID=kwargs.get('submissionID')  
        
        user=User.objects.get(username=userName)
        if user is None:
            return HttpResponse(content='User not found', status=404) 
        
        survey=Survey.objects.get(SurveyID=surveyID)
        if survey is None:
            return HttpResponse(content='Questionnaire not found', status=404) 
          
        
        #从问卷广场界面进入：查找该用户是否有该问卷未提交的填写记录
        if submissionID=="-1":
            submission_query=Submission.objects.filter(Respondent=user,Survey=survey,Status='Unsubmitted')
            if submission_query.exists():
                submissionID=submission_query.first().SubmissionID  #找到未填写的记录
                duration=submission_query.first().Interval
                submission = submission_query.first()
                # newsubmissionID = submissionID
            
            else:      #不存在：创建一条新的填写记录
                submission=Submission.objects.create(Survey=survey,Respondent=user,Status="Unsubmitted",
                                                    Interval=0)
                duration=0
                submissionID=submission.SubmissionID
                # newsubmissionID = submission.SubmissionID
                # return HttpResponse(content='Submission not existed', status=404) 
        
        #从问卷管理界面进入：
        else:
            print("TieZhuGieGie")
            submission=Submission.objects.filter(SubmissionID=submissionID)
            print(submission)
            print(submissionID)
            print("TieZhuGieGie")
            '''if not submission.exists():
                print("TieZhuGieGie")
                return HttpResponse(content='Submission not found', status=404) '''
            
            #submissionID=-2时,只传回问卷题干
            if submissionID=="-2":
                data={'Title':survey.Title,'category':survey.Category,'TimeLimit':survey.TimeLimit,
                'description':survey.Description,'duration':0}
                return JsonResponse(data)
        
            duration=submission.Interval
        
        Title=survey.Title
        Description=survey.Description
        category=survey.Category
        TimeLimit=survey.TimeLimit
        #people=survey.QuotaLimit
        
        '''1.以下部分与问卷编辑界面的get函数类似，拿到题干'''
        '''2.拿到当前submissionID对应填写记录'''
        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionID','QuestionNumber').all())
                                                    
        all_questions_list = list(all_questionList_iterator)

        # 将迭代器转换为列表 (按QuestionNumber递增排序)--顺序展示
        if survey.IsOrder:
            all_questions_list.sort(key=lambda x: x['QuestionNumber']) 
        
        #print(all_questions_list.length())
        questionList=[]
        #print(all_questions)
        for question in all_questions_list:
            if question["Category"]==1 or question["Category"]==2:    #选择题

                #该单选题的用户选项:当前问卷当前submission(如果用户未选，则找不到对应的答案记录)
                if question["Category"]==1:
                    optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])  #只有一条记录
                    #用户未填该单选题
                    if not optionAnswer_query.exists():
                        answer=-1
                    #用户填了这个单选题，有一条答案记录
                    else:
                        answer=optionAnswer_query.first().ChoiceOptions.OptionID
                
                #该多选题的用户选项:当前问卷当前submission
                else:
                    optionAnswer_query=ChoiceAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])#一或多条记录
                    #用户未填该多选题
                    if not optionAnswer_query.exists():answer=[]
                    #用户填了这个多选题，有一条/多条答案记录
                    else:
                        answer=[]
                        for optionAnswer in optionAnswer_query:
                            answer.append(optionAnswer.ChoiceOptions.OptionID)

                optionList=[]
                #将所有选项顺序排列
                options_query=ChoiceOption.objects.filter(Question=question["QuestionID"]).order_by('OptionNumber')
                for option in options_query:
                    optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,'optionId':option.OptionID})
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                     'optionList':optionList,'Answer':answer})
                
            elif question["Category"]==3:                  #填空题
                #该填空题的用户答案:有且仅有一条记录
                blankAnswer_query=BlankAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
                #用户未填该填空题
                if not blankAnswer_query.exists():
                    answer=""
                else:
                    answer=blankAnswer_query.first().Content
                
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],
                                     'correctAnswer':question["CorrectAnswer"],'Answer':answer})

            elif question["Category"]==4:                  #评分题
                
                #该评分题的用户答案:有且仅有一条记录
                ratingAnswer_query=RatingAnswer.objects.filter(Submission=submission,Question=question["QuestionID"])
                #用户未填该评分题
                if not ratingAnswer_query.exists():
                    answer=0
                else:
                    answer=ratingAnswer_query.first().Rate

                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'Answer':answer})


        #传回题干和填写记录
        else:
            data={'Title':survey.Title,'category':survey.Category,'TimeLimit':survey.TimeLimit,
              'description':survey.Description,'questionList':questionList,'duration':duration, 'submissionID':submissionID}
            return JsonResponse(data)
        

#问卷填写界面：从前端接收用户的填写记录(POST)
def get_submission(request):
    if(request.method=='POST'):
        try:
            print("start get_submission")
            body=json.loads(request.body)
            surveyID=body['surveyID']    #问卷id
            status=body['status']  #填写记录状态
            submissionID=body['submissionID']   #填写记录ID
            username=body['username']     #填写者
            submissionList=body['question']     #填写记录
            duration=body['duration']  

            score=body['score'] 

            print(submissionList)

            survey=Survey.objects.get(SurveyID=surveyID)
            if survey is None:
                return HttpResponse(content='Questionnaire not found',status=404)
            
            user=User.objects.get(username=username)
            if user is None:
                return HttpResponse(content='User not found',status=404)

            #当前不存在该填写记录，创建：
            if submissionID==-1:
                submission=Submission.objects.create(Survey=survey,Respondent=user,
                                             SubmissionTime=timezone.now(),Status=status,
                                             Interval=0,Score=score)
            
            #已存在，删除填写记录的所有内容
            else:
                submission=Submission.objects.get(SubmissionID=submissionID)
                if submission is None:
                    return HttpResponse(content='Submission not found',status=404)
                submission.Score=score
                submission.Status=status
                submission.save()
                
                #所有选择题的填写记录
                ChoiceAnswer_query=ChoiceAnswer.objects.filter(Submission=submission)
                if ChoiceAnswer_query.exists():
                    for choiceAnswer in ChoiceAnswer_query:
                        choiceAnswer.delete()
                
                #所有填空题的填写记录
                BlankAnswer_query=BlankAnswer.objects.filter(Submission=submission)
                if BlankAnswer_query.exists():
                    for blankAnswer in BlankAnswer_query:
                        blankAnswer.delete()
                
                #所有评分题的填写记录
                RatingAnswer_query=RatingAnswer.objects.filter(Submission=submission)
                if RatingAnswer_query.exists():
                    for ratingAnswer in RatingAnswer_query:
                        ratingAnswer.delete()

            for submissionItem in submissionList:
                print("TieZhu")
                questionID=submissionItem["questionID"]     #问题ID
                answer=submissionItem['value']        #用户填写的答案
                category=submissionItem['category']     #问题类型（用于后续区分，解决不同种类问题的QuestionID会重复的问题）

                #print(category)
                #question = BaseQuestion.objects.get(QuestionID=questionID).select_subclasses()   #联合查询

                '''
                question_iterator=itertools.chain(ChoiceQuestion.objects.filter(QuestionID=questionID),
                                                    BlankQuestion.objects.filter(QuestionID=questionID),
                                                    RatingQuestion.objects.filter(QuestionID=questionID))
                question_list=list(question_iterator)
                question=question_list[0]
                print(question)
                print(question_list)
                # print(question["Category"])
                # print(question.Category)'''

                questionNewList=[]
                choiceQuestion_query=ChoiceQuestion.objects.filter(QuestionID=questionID,Category=category)
                if choiceQuestion_query.exists():
                    questionNewList.append(choiceQuestion_query.first())

                blankQuestion_query=BlankQuestion.objects.filter(QuestionID=questionID,Category=category)
                if blankQuestion_query.exists():
                    questionNewList.append(blankQuestion_query.first())

                ratingQuestion_query=RatingQuestion.objects.filter(QuestionID=questionID,Category=category)
                if ratingQuestion_query.exists():
                    questionNewList.append(ratingQuestion_query.first())
                
                question=questionNewList[0]
                
                print("123154654")

                # print(question.CorrectAnswer)
                if question is None:
                    return HttpResponse(content='Question not found',status=404)

                if question.Category==1:     #单选题：Answer为选项ID
                    if answer==-1: continue       #返回-1，代表用户没填该单选题
                    option=ChoiceOption.objects.get(OptionID=answer)     #用户选择的选项
                    if option is None:
                        return HttpResponse(content="Option not found",status=404)
                    choiceAnswer=ChoiceAnswer.objects.create(Question=question,Submission=submission,ChoiceOptions=option)
                    choiceAnswer.save()

                    #若已提交，报名问卷的必填选择题中，选择的对应选项-1
                    if status=='Submitted' and survey.Category==2 and question.IsRequired==True:
                        if option.MaxSelectablePeople<=0:
                            data={'message':'People exceeds'}
                            return JsonResponse(data)
                        else:
                            option.MaxSelectablePeople-=1

                elif question.Category==2:     #多选题：Answer为选项ID的数组
                    #为每个用户选择的选项，创建一条ChoiceAnswer记录
                    for optionID in answer:
                        option=ChoiceOption.objects.get(OptionID=optionID)     #用户选择的选项
                        if option is None:
                            return HttpResponse(content="Option not found",status=404)
                        choiceAnswer=ChoiceAnswer.objects.create(Question=question,Submission=submission,ChoiceOptions=option)
                        choiceAnswer.save()

                elif question.Category==3:     #填空题：answer为填写的内容
                    blankAnswer=BlankAnswer.objects.create(Question=question,Submission=submission,Content=answer)
                    blankAnswer.save()
                
                elif question.Category==4:      #评分题：answer为填写的内容
                    print(answer)
                    ratingAnswer=RatingAnswer.objects.create(Question=question,Submission=submission,Rate=answer)
                    ratingAnswer.save()

                #若已提交，报名问卷的必填选择题中，选择的对应选项-1
                if status=='Submitted':
                    #该问卷所有必填选择题(一定有人数限制)
                    choiceQuestion_query=ChoiceQuestion.objects.filter(Survey=survey,Category__in=[1,2])
                    if not choiceQuestion_query.exists():
                        return HttpResponse(content="Choice questions not found",status=404)
                    
                    #该必填选择题的当前填写记录内容
                    choiceAnswer=ChoiceAnswer.objects.filter(Question=question,Submission=submission)
                    for choiceQuestion in choiceQuestion_query:
                        choiceOption_query=ChoiceOption.objects.filter(Question=question)

                
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    data={'message':True,'submissionId':submissionID}
    print(submissionID)
    return JsonResponse(data)
    #return JsonResponse({'error': 'Invalid request method'}, status=405)


#问卷编辑界面：向前端传输问卷设计内容
class GetQuestionnaireView(APIView):
    def get(self, request, survey_id, *args, **kwargs):  
        design = request.GET.get('design', 'false')  # 默认为'false'  
        design = design.lower() == 'true'  # 将字符串转换为布尔值  
        survey=Survey.objects.get(SurveyID=survey_id)
        if survey is None:
            return HttpResponse(content='Questionnaire not found', status=400) 
        title=survey.Title
        catecory=survey.Category
        #people=survey.QuotaLimit
        TimeLimit=survey.TimeLimit

        '''
        blank_questions = list(BlankQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  
        choice_questions = list(ChoiceQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  
        rating_questions = list(RatingQuestion.objects.filter(Survey=survey).values_list('id', 'QuestionNumber'))  

        # 将这些列表合并，并基于QuestionNumber进行排序  
        combined_questions = sorted(chain(blank_questions, choice_questions, rating_questions), key=lambda x: x[1])
        '''

        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionNumber','QuestionID').all())
                                                    
        # 将迭代器转换为列表  
        all_questions_list = list(all_questionList_iterator)
        all_questions_list.sort(key=lambda x: x['QuestionNumber']) 

        questionList=[]

        #print(all_questions)
        for question in all_questions_list:
            if question["Category"]==1 or question["Category"]==2:    #选择题
                optionList=[]
                #将所有选项顺序排列
                options_query=ChoiceOption.objects.filter(Question=question["QuestionID"]).order_by('OptionNumber')
                for option in options_query:
                    optionList.append({'content':option.Text,'optionNumber':option.OptionNumber,'isCorrect':option.IsCorrect,
                                       'optionID':option.OptionID,'MaxSelectablePeople':option.MaxSelectablePeople})
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'optionCnt':question["OptionCnt"],
                                     'optionList':optionList})
                
            elif question["Category"]==3:                  #填空题
                
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"],'correctAnswer':question["CorrectAnswer"]})

            elif question["Category"]==4:                  #评分题
                questionList.append({'type':question["Category"],'question':question["Text"],'questionID':question["QuestionID"],
                                     'isNecessary':question["IsRequired"],'score':question["Score"]})

        
        data={'Title':survey.Title,'category':survey.Category,'TimeLimit':survey.TimeLimit,
              'description':survey.Description,'questionList':questionList}
        
        return JsonResponse(data, status=200)


#问卷编辑界面：从前端接收问卷的设计内容
def save_qs_design(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            surveyID=body['surveyID']    #问卷id
            title=body['title']  #问卷标题
            catecory=body['category']   #问卷类型（普通0、投票1、报名2、考试3）
            isOrder=body['isOrder'] #是否顺序展示（考试问卷）
            #people=body['people']   #报名人数（报名问卷）
            timelimit=body['timeLimit']
            username=body['userName']   #创建者用户名
            description=body['description'] #问卷描述
            Is_released=body['Is_released'] #保存/发布

            questionList=body['questionList']   #问卷题目列表
            # print(questionList)
            user=User.objects.get(username=username)
            if user is None:        
                return HttpResponse(content='User not found', status=400) 
            

            #当前不存在该问卷，创建：
            if surveyID==-1:
                survey=Survey.objects.create(Owner=user,Title=title,
                                             Description=description,Is_released=Is_released,
                                             Is_open=True,Is_deleted=False,Category=catecory,
                                             TotalScore=0,TimeLimit=timelimit,IsOrder=isOrder
                                            )
                #survey.QuotaLimit=people
            #已有该问卷的编辑记录
            else:
                survey=Survey.objects.get(SurveyID=surveyID)
                if survey is None:
                    return HttpResponse(content='Questionnaire not found', status=400) 
                
                survey.Title=title
                survey.Is_released=Is_released
                survey.Description=description
                survey.Category=catecory
                survey.TimeLimit=timelimit
                survey.IsOrder=isOrder
                #survey.QuotaLimit=people    #该问卷的报名人数
                survey.save()

                #该问卷的所有选择题
                choiceQuestion_query=ChoiceQuestion.objects.filter(Survey=survey)
                for choiceQuestion in choiceQuestion_query:
                    #删除该选择题的所有选项
                    choiceOption_query=ChoiceOption.objects.filter(Question=choiceQuestion)
                    for choiceOption in choiceOption_query:
                        choiceOption.delete()
                    choiceQuestion.delete()

                #删除该问卷的所有填空题
                blankQuestion_query=BlankQuestion.objects.filter(Survey=survey)
                for blankQuestion in blankQuestion_query:
                    blankQuestion.delete()
                
                #删除该问卷的所有评分题
                ratingQuestion_query=RatingQuestion.objects.filter(Survey=survey)
                for ratingQuestion in ratingQuestion_query:
                    ratingQuestion.delete()

            index=1
            for question in questionList:
                if question["type"]==1 or question["type"]==2:        #单选/多选

                    print("---")
                    optionList=question['optionList']

                    question=ChoiceQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                                QuestionNumber=index,Score=question["score"],Category=question["type"],
                                                                OptionCnt=question["optionCnt"])
                    question.save()
                    #所有选项:
                    jdex=1
                    for option in optionList:
                        print(option['MaxSelectablePeople'])
                        option=ChoiceOption.objects.create(Question=question,Text=option["content"],IsCorrect=option["isCorrect"],
                                                           OptionNumber=jdex,MaxSelectablePeople=option['MaxSelectablePeople'])
                        option.save()
                        jdex=jdex+1

                        print("***")
                
                elif question["type"]==3:                          #填空
                    # print(question)
                    question=BlankQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                        Score=question["score"],QuestionNumber=index,Category=question["type"],
                                                            CorrectAnswer=question["correctAnswer"])
                    question.save()  
                
                else:                                           #评分题
                    question=RatingQuestion.objects.create(Survey=survey,Text=question["question"],IsRequired=question["isNecessary"],
                                                              Score=question["score"],QuestionNumber=index,Category=question["type"])
                    question.save()
                index=index+1
            return HttpResponse(content='Questionnaire saved successfully', status=200) 
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)


#填写记录
def delete_filled_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            submissionID=body
            submission=Submission.objects.get(SubmissionID=submissionID)     #对应填写记录
            if submission is None:
                return JsonResponse({'error': 'No ID provided'}, status=400) 
            submission.delete()

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    data = {"message": "True"}
    return JsonResponse(data)

def update_or_delete_released_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            flag=body['flag']

        #创建者删除已发布的问卷(将问卷状态改为Is_deleted=True)
        #所有该问卷填写者处，该问卷的状态修改为已删除；填写者刷新问卷管理界面，保留被删除项，但无法继续填写
            if flag==1:
                qsID=body['id']
                if qsID is None:
                    return JsonResponse({'error': 'No ID provided'}, status=400) 
                qs=Survey.objects.filter(SurveyID=qsID).first()     #对应问卷
                qs.Is_deleted=True
                qs.Is_released=False
                qs.save()

                submission_query=Submission.objects.filter(Survey=qs)   #该问卷的所有填写记录
            
                # 使用 for 循环遍历 submission_query  
                with transaction.atomic():  # 你可以使用事务确保操作的原子性  
                    for submission in submission_query:  
                        #该填写已提交：状态不变
                        #该填写未提交：填写状态改为'Deleted'(已被创建者删除)
                        if submission.Status=='Unsubmitted':
                            submission.Status='Deleted'
                            submission.save()
                
            
            #更新发布状态
            else:
                qsID=body['id']
                if qsID is None:
                    return JsonResponse({'error': 'No ID provided'}, status=400) 
                qs=Survey.objects.filter(SurveyID=qsID).first()     #对应问卷

                #当前未发布，改为发布状态：
                if qs.Is_open==False:
                    qs.Is_open=True
                
                #当前已发布，撤回
                else:
                    qs.Is_open=False
                qs.save()

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    data={"message":"True"}
    return JsonResponse(data)
    #return JsonResponse({'error': 'Invalid request method'}, status=405)


#删除未发布的问卷(直接从数据库移除)
def delete_unreleased_qs(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            qsID=body
            if qsID is None:
                return JsonResponse({'error': 'No ID provided'}, status=400) 
            qs=Survey.objects.filter(SurveyID=qsID).first()
            if qs is None:  
                return JsonResponse({'error': 'No questionnaire found with the given ID'}, status=404)
            qs.delete()

            data={'message':'True'}
            return JsonResponse(data)
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户已创建未发布的问卷
def get_drafted_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        qs_query=Survey.objects.filter(Owner=user,Is_released=False)
        data_list=[{'Title':survey.Title,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,'Category':survey.Category} for survey in qs_query]
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户发布的问卷
def get_released_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        qs_query=Survey.objects.filter(Owner=user,Is_released=True,Is_deleted=False)    #不显示已删除问卷

        data_list=[]
        for survey in qs_query:
            submissionCnt=Submission.objects.filter(Survey=survey).count()  #该问卷已提交的填写份数
            data_list.append({'Title':survey.Title,'PublishDate':survey.PublishDate,'SurveyID':survey.SurveyID,
                    'Category':survey.Category,'Description':survey.Description,'FilledPeople':submissionCnt, 'IsOpening':survey.Is_open})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#当前用户的填写记录(包括被创建者删除的问卷的填写记录)
def get_filled_qs(request,username):
    if(request.method=='GET'):
        user=User.objects.get(username=username)
        submission_query=Submission.objects.filter(Respondent=user)
        data_list=[]

         # 使用 for 循环遍历 submission_query  
        with transaction.atomic():  # 你可以使用事务确保操作的原子性  
            for submission in submission_query:
                status=submission.Status
                if status=="Unsubmitted":
                    status_Chinese="未提交"
                elif status=="Submitted" or status=="Graded":
                    status_Chinese="已提交"
                else:
                    status_Chinese="已删除"
                data_list.append({'Title':submission.Survey.Title,'PublishDate':submission.Survey.PublishDate,
                                  'SurveyID':submission.Survey.SurveyID,'Category':submission.Survey.Category,
                                  'Description':submission.Survey.Description,'Status':status_Chinese,
                                  'SubmissionID':submission.SubmissionID})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#问卷管理界面：进入填写时，检查当前问卷的Is_open状态；若为False，则创建者已暂停收集，不可再填写
def check_qs_open_stautus(request,questionnaireId):
    qs=Survey.objects.get(SurveyID=questionnaireId)
    if qs is None:
        return HttpResponse(content="Questionnaire not found",status=404)
    if qs.Is_open==False:
        data={"message":False,"content":"该问卷已暂停收集"}
        return JsonResponse(data)
    else:
        data={"message":True,"content":"可开始/修改填写"}

#问卷广场：检查投票/考试问卷
def check_qs(request,username,questionnaireId,type):
    user=User.objects.get(username=username)
    if user is None:
        return HttpResponse(content="User not found",status=404)
    qs=Survey.objects.get(SurveyID=questionnaireId)
    if qs is None:
        return HttpResponse(content="Questionnaire not found",status=404)
    
    #投票问卷:每个用户只可提交一次
    if qs.Category==1:
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)
        if submission_query.exists():
            submission=submission_query.first()
            if submission.Status=='Unsubmitted':
                data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
            elif submission.Status=='Submitted':
                data={'message':False,"content":"您完成投票，不可重复投票"}
            else:
                data={'message':False,"content":"当前问卷已被撤回"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)
    
    #考试问卷：每个用户只可提交一次
    elif qs.Category==3:
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)
        if submission_query.exists():
            submission=submission_query.first()
            if submission.Status=='Unsubmitted':
                data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
            elif submission.Status=='Graded':
                data={'message':False,"content":"您已完成当前考试"}
            else:
                data={'message':False,"content":"当前问卷已被撤回"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)
    
    #报名问卷：超过人数，不可以再报名
    elif qs.Category==2:
        #检查是否超人数(检查每个必填选择题的所有选项，是否都超人数)
        submission_query=Submission.objects.filter(Respondent=user,Survey=qs)

        choiceQuestion_query=ChoiceQuestion.objects.filter(Survey=qs,Category__in=[1,2],IsRequired=True)
        if choiceQuestion_query.exists():
            #每个必填选项
            for choiceQuestion in choiceQuestion_query:
                isFull=True
                choiceOption_query=ChoiceOption.objects.filter(Question=choiceQuestion)
                #每个选项的剩余人数
                for choiceOption in choiceOption_query:
                    if choiceOption.MaxSelectablePeople>0:
                        isFull=False
                
                if isFull==True:
                    data={'message':False,"content":"当前报名人数已满"}
                    return JsonResponse(data)

        '''
        currentCnt=Submission.objects.filter(Respondent=user,Survey=qs).count()

        if currentCnt>=qs.QuotaLimit:
            data={'message':False,"content":"当前报名人数已满"}
            return JsonResponse(data)
        '''

        #检查是否有未提交的填写记录
        unsubmitted_query=Submission.objects.filter(Respondent=user,Survey=qs,Status="Unsubmitted")
        if unsubmitted_query.exists():
            data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
        
        data={'message':"True","content":"可以开始/继续填写"}
        return JsonResponse(data)   

    #普通问卷
    else: 
        #检查是否有未提交的填写记录
        unsubmitted_query=Submission.objects.filter(Respondent=user,Survey=qs,Status="Unsubmitted")
        if unsubmitted_query.exists():
            data={'message':False,"content":"对于当前问卷，您有未提交的填写记录"}
        else:
            data={'message':"True","content":"可以开始/继续填写"}

        return JsonResponse(data)   
    
#问卷广场：所有问卷
def get_all_released_qs(request):
    if(request.method=='GET'):
        qs_query=Survey.objects.filter(Is_released=True,Is_open=True).order_by("-PublishDate")
        data_list=[]

        for survey in qs_query:
            reward=RewardOffering.objects.filter(Survey=survey).first()
            if reward is not None:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,
                                  'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,
                                  'Reward':reward.Zhibi,'HeadCount':reward.AvailableQuota})
            else:
                data_list.append({'Title':survey.Title,'PostMan':survey.Owner.username,'PublishDate':survey.PublishDate,
                                  'SurveyID':survey.SurveyID,'categoryId':survey.Category,'Description':survey.Description,
                                  'Reward':None})
        data={'data':data_list}
        return JsonResponse(data)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


'''个人中心界面'''
#购买商店中的头像
def modify_photo_in_shop(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            username=body['username']
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 
            
            photonumber = body['photonumber']
            status = body['status']
            #修改头像
            photonumber = body['photonumber']
            status = body['status']
            user.set_array_element(photonumber,status)

            #修改纸币
            zhibi=body['money']
            user.zhibi=zhibi
            user.save()
            
            photos_data = json.loads(user.own_photos)  
            data={'ownphotos':photos_data}
            return JsonResponse(data)

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#获取个人信息
def get_user_info(request,username):
    if(request.method=='GET'):
        try:
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 
            
            photo=user.get_used_element()
            data={'password':user.password,'email':user.email,'zhibi':user.zhibi,'photo':photo}
            return JsonResponse(data)
        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    return JsonResponse({'error': 'Invalid request method'}, status=405)

#修改个人信息
def modify_user_info(request):
    if(request.method=='POST'):
        try:
            body=json.loads(request.body)
            username=body['username']
            flag=body['flag']
            user=User.objects.get(username=username)
            if user is None:
                return JsonResponse({'error': 'No user found'}, status=400) 

            #修改除头像外的其他信息
            if flag==1:
                email=body['email']
                password=body['password']
                user.email=email
                user.password=password
                user.save()
            
            #修改头像：
            elif flag==2:
                photonumber = body['photonumber']
                status = body['status']
                user.set_array_element(photonumber,status)
                user.save()
            
            else:
                # 参数不正确或缺失  
                return JsonResponse({'error': 'Invalid or missing parameters'}, status=400)

        except json.JSONDecodeError:  
            return JsonResponse({'error': 'Invalid JSON body'}, status=400)
        except Exception as e:  
            return JsonResponse({'error': str(e)}, status=500) 
    data={"message":"True"}
    return JsonResponse(data)


class Token:
    def __init__(self, security_key):
        self.security_key = security_key
        # salt是秘钥的编码
        self.salt = base64.encodebytes(security_key.encode('utf-8'))
        #security_key是settings.py中SECURITY_KEY
        #salt是经过base64加密的SECURITY_KEY

    # 生成token,token中可以保存一段信息，这里我们选择保存username
    def generate_validate_token(self, username):
        serializer = utsr(self.security_key)            #生成令牌serializer
        return serializer.dumps(username, self.salt)    #username在令牌中被编码
        #将带有token的验证链接发送至注册邮箱

    # 验证token
    def confirm_validate_token(self, token, expiration=3600):
        serializer = utsr(self.security_key)
        return serializer.loads(token, salt=self.salt, max_age=expiration)

    # 删除token
    def remove_validate_token(self, token):
        serializer = utsr(self.security_key)
        return serializer.loads(token, salt=self.salt)

token_confirm = Token(django_settings.SECRET_KEY)
def get_token(request):

    url = serveAddress+'user/' + token_confirm.generate_validate_token(username='username')
    '''此处将这个url发送到客户邮箱，我们这里就不进行邮件发送的操作了'''
    return HttpResponse(status=200,content=True)

def send_registration_email(request):
    if(request.method=='POST'):
        body=json.loads(request.body)
        username=body['username']
        password=body['password']
        email=body['email']


        if(email==False):
            user_queryset=User.objects.filter(username=username)
            user=user_queryset.first()
            #return HttpResponse(status=200,content=username)
            if not user_queryset.exists():
                data={'message':"1"}
                return JsonResponse(data)
                #return HttpResponse(status=200,content="1")
            elif(password!=user.password):
                data={'message':"2"}
                return JsonResponse(data)
                #return HttpResponse(status=200,content="2")
            else:
                photos_data = json.loads(user.own_photos)  
                data={
                    'message':"0",
                    'username':user.username,
                    'password':user.password,
                    'email':user.email,
                    'ownphotos':photos_data,
                    'zhibi':user.zhibi,
                }
            return JsonResponse(data)

        user1=User.objects.filter(username=username)
        if user1.exists():
            return HttpResponse(status=200,content=False)

        #创建新用户(尚未邮箱验证,非有效用户)
        user=User.objects.create(username=username,email=email,
                                     password=password,CreateDate=timezone.now(),isActive=False)
        user.save()

        #生成令牌
        token = token_confirm.generate_validate_token(username)
        #active_key = base64.encodestring(userName)
        url="/login"

        #发送邮件
        subject="'纸翼传问'新用户注册"
        message=("Hello,"+username+"! 欢迎注册“纸翼传问”!\n"
                     +"请点击以下链接，以激活新账户:\n"
                     +serveAddress+url+token)

        email=EmailMessage(subject=subject,body=message,from_email="1658441344@qq.com",
                            to=[email],reply_to=["1658441344@qq.com"])
        #email.attach_file('/images/weather_map.png')
        email.send()

        return HttpResponse("请查看邮箱，按照提示激活账户。"
                                "(验证链接只在一小时内有效).")
    return HttpResponse(status=200,content=True)

#用户点击邮箱链接,调用视图activate_user(),验证激活用户:
def activate_user(request,token):
    try:username=token_confirm.confirm_validate_token(token)
    except:
        return HttpResponse("抱歉，验证链接已过期，请重新注册。")
    try:user=User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponse("抱歉，当前用户不存在，请重新注册。")
    user.is_active=True
    user.save()
    return HttpResponse(status=200,content=True)

#额外需要的包
import pandas as pd
from io import BytesIO
import openpyxl

#交叉分析
def cross_analysis(request, QuestionID1, QuestionID2):
    if request.method == 'GET':
        
        question1 = ChoiceQuestion.objects.get(QuestionID=QuestionID1)
        question2 = ChoiceQuestion.objects.get(QuestionID=QuestionID2)

        if QuestionID1 is None or QuestionID2 is None:
            return JsonResponse({'error': 'Missing QuestionID(s)'}, status=400)
        survey = question1.Survey
        
        results = {'list': []}
        for options1 in question1.choice_options.all():
            for options2 in question2.choice_options.all():
                cnt = 0
                for submission in Submission.objects.filter(Survey=survey):
                    if ChoiceAnswer.objects.filter(Submission=submission, ChoiceOptions=options1).exists() and ChoiceAnswer.objects.filter(Submission=submission, ChoiceOptions=options2).exists():
                        cnt += 1
                results['list'].append({
                    'content': f"{options1.Text}-{options2.Text}",
                    'cnt': cnt
                })
                
        
        return JsonResponse(results)

#下载表格
def download_submissions(request, surveyID):
    if request.method == 'GET':
        survey = Submission.objects.filter(Survey__SurveyID=surveyID).first().Survey
        submissions = Submission.objects.filter(Survey__SurveyID=surveyID, Status__in=['Submitted', 'Graded'])

        data = {
            '填写者': [],
            '提交时间': [],
        }

        if survey.Category == '3':
            data['分数'] = []
            

        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionNumber','QuestionID').all())
                                                    
        # 将迭代器转换为列表  
        questions = list(all_questionList_iterator)
        questions.sort(key=lambda x: x['QuestionNumber']) 
        

        for q in questions:
            if q["Category"] < 3:
                question = ChoiceQuestion.objects.get(QuestionID=q["QuestionID"])
            elif q["Category"] == 3:
                question = BlankQuestion.objects.get(QuestionID=q["QuestionID"])
            elif q["Category"] == 4:
                question = RatingQuestion.objects.get(QuestionID=q["QuestionID"])
            data[question.Text] = []


        for submission in submissions:
            data['填写者'].append(submission.Respondent.username)
            data['提交时间'].append(submission.SubmissionTime.date)

            if survey.Category == '3':
                data['分数'].append(submission.Score)

            all_answer = itertools.chain(BlankAnswer.objects.filter(Submission=submission).values('AnswerID').all(),
                                         ChoiceAnswer.objects.filter(Submission=submission).values('AnswerID').all(),
                                         RatingAnswer.objects.filter(Submission=submission).values('AnswerID').all())
                                                    
            answers = list(all_answer)

            for a in answers:
                if ChoiceAnswer.objects.filter(AnswerID=a["AnswerID"]).exists():
                    answer = ChoiceAnswer.objects.get(AnswerID=a["AnswerID"])
                    choices = [chr(ord('A') + answer.ChoiceOptions.OptionNumber - 1)]
                    data[answer.Question.Text].append(', '.join(choices))
                    
                elif BlankAnswer.objects.filter(AnswerID=a["AnswerID"]).exists():
                    answer = BlankAnswer.objects.get(AnswerID=a["AnswerID"])
                    data[answer.Question.Text].append(answer.Content)
                    
                elif RatingAnswer.objects.filter(AnswerID=a["AnswerID"]).exists():
                    answer = RatingAnswer.objects.get(AnswerID=a["AnswerID"])
                    data[answer.Question.Text].append(answer.Rate)


        df = pd.DataFrame(data)
        output = BytesIO()
    # 创建Excel writer对象
        writer = pd.ExcelWriter(output, engine='openpyxl')

    # 将DataFrame写入Excel文件
        df.to_excel(writer, index=False)

    # 保存Excel文件
        writer.save()

    # 重置流的位置
        output.seek(0)

    # 创建HttpResponse对象，将Excel文件作为响应发送
        response = HttpResponse(
            output.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=文件名.xlsx'

        return response
        '''
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="问卷填写情况.xlsx"'
        df.to_excel(response, index=False)

        return response
        '''
    return JsonResponse({'error': 'Invalid request method'}, status=405)

from django.db.models import Count, Sum, Q

def survey_statistics(request, surveyID):
    if (request.method=='GET'):

        survey = Survey.objects.get(SurveyID=surveyID)
        survey_stat = SurveyStatistic.objects.get(Survey=survey)
        #问卷基础信息
        stats = {
            'title': survey.Title,
            'description': survey.Description,
            'category': survey.Category,
            'total_submissions': survey_stat.TotalResponses,
            'max_participants': survey.QuotaLimit if survey.QuotaLimit else None,
            'average_score': survey_stat.AverageScore,
            'questionList': []
        }
        
        all_questionList_iterator = itertools.chain(BlankQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','CorrectAnswer','QuestionNumber','QuestionID').all(),
                                                    ChoiceQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','OptionCnt','QuestionNumber','QuestionID').all(),
                                                    RatingQuestion.objects.filter(Survey=survey).values('Category', 'Text', 'QuestionID', 'IsRequired', 'Score','QuestionNumber','QuestionID').all())                              
        # 将迭代器转换为列表  
        questions = list(all_questionList_iterator)
        questions.sort(key=lambda x: x['QuestionNumber']) 
        #题目信息
        for q in questions:
            if q["Category"] < 3:
                question = ChoiceQuestion.objects.get(QuestionID=q["QuestionID"])
            elif q["Category"] == 3:
                question = BlankQuestion.objects.get(QuestionID=q["QuestionID"])
            elif q["Category"] == 4:
                question = RatingQuestion.objects.get(QuestionID=q["QuestionID"])
            
            q_stats = {
                'type': question.Category,
                'questionId': question.QuestionID,
                'question': question.Text,
                'number': question.QuestionNumber,
                'is_required': question.IsRequired,
                'score': question.Score if survey.Category == '3' else None,
                'correct_answer': None,
                'correct_count': 0,
                'options_stats': [],
                'rating_stats': [],
                'blank_stats': []
            }
    
            #答案信息
            if question.Category < 3:
                for option in question.choice_options.all():
                    option_stats = {
                        'number': option.OptionNumber,
                        'is_correct': option.IsCorrect,
                        'optionContent': option.Text,
                        'optionCnt': ChoiceAnswer.objects.filter(Question=question, ChoiceOptions=option).count()
                    }
                    q_stats['options_stats'].append(option_stats)
                
                correct_option_numbers = [option.Number for option in question.choice_options.filter(IsCorrect=True)]
                q_stats['correct_answer'] = correct_option_numbers
                
                correct_submissions = set()
                for correct_number in correct_option_numbers:
                    submissions_with_correct_option = ChoiceAnswer.objects.filter(
                        Question=question,
                        ChoiceOptions__Number=correct_number
                    ).values_list('Submission', flat=True)
    
                    # 更新完全正确回答的提交集合
                    if not correct_submissions:
                        correct_submissions = set(submissions_with_correct_option)
                    else:
                        correct_submissions.intersection_update(submissions_with_correct_option)

                q_stats['correct_count'] = len(correct_submissions)
            
            elif question.Category == 4:
                ratings = RatingAnswer.objects.filter(Question=question).values('rate').annotate(count=Count('rate'))
                for rating in ratings:
                    q_stats['rating_stats'].append({
                        'optionContent': rating['rate'],
                        'optionCnt': rating['count']
                    })
    
            elif question.Category == 3:  
                answers = BlankAnswer.objects.filter(Question=question).values('content').annotate(count=Count('content'))
                for answer in answers:
                    q_stats['blank_stats'].append({
                        'fill': answer['content'],
                        'cnt': answer['count']
                    })
                    
            stats['questionList'].append(q_stats)
        return JsonResponse(stats)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

