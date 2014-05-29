from django.conf.urls import patterns, include, url
import models



urlpatterns = patterns('leaderboard.board_views',
    url(r'^board/(\d+)/?$', 'detail'),
    url(r'^board/post_challenge/(\d+)/?$', 'post_challenge_detail'),
    url(r'^board/post_challenge/?$', 'post_challenge_index'),
    url(r'^board/?$', 'index'),
	url(r'^board/(\d+)/submitted/?$', 'submitted'),
	url(r'^board/(\d+)/submit/?$', 'submit'),

)

urlpatterns += patterns('leaderboard.team_views',
    url(r'^team/(\d+)/?$', 'detail'),
    url(r'^team/?$', 'index'),
    url(r'^team/setup/?$', 'setup'),
    url(r'^team/create/?$', 'create'),
    url(r'^team/join/?$', 'join'),
    url(r'^team/request_join/(\d+)/?$', 'request_join'),
    url(r'^team/accept/(?P<token>\w+)/$', 'accept'),
    url(r'^team/reject/(?P<token>\w+)/$', 'reject'),

)

urlpatterns += patterns('leaderboard.entry_views',
    url(r'^entry/(\d+)/?$', 'detail'),

)
urlpatterns += patterns('leaderboard.views',
	url(r'^$', 'front_page'),
	)


urlpatterns += patterns('leaderboard.data_views',
    url(r'^data/?$', 'index'),
    url(r'^data/admin/(\S+)/?$', 'admin_file'),
    url(r'^data/public/(\S+)/?$', 'public_file'),
	)