"""Due Sunday-20:00 review, executed by the existing replenishment workflow.

Only GETs Facebook. A durable completed cutoff prevents duplicate reviews.
GitHub cron may run late; it never controls Facebook's publication clock.
"""
import datetime as dt
import json
import os
import meta_graph_publish as base
import meta_native_schedule as native
import performance_review as three_day

ROOT = base.ROOT
FIRST_CUTOFF = dt.datetime(2026, 11, 1, 20, tzinfo=base.TZ)
FIELDS = 'id,message,created_time,is_published,reactions.limit(0).summary(true),comments.limit(0).summary(true),shares'
BASIC_FIELDS = 'id,message,created_time,is_published'


def due_cutoff(now):
    local = now.astimezone(base.TZ)
    sunday = local.date() - dt.timedelta(days=(local.weekday() + 1) % 7)
    cutoff = dt.datetime.combine(sunday, dt.time(20), base.TZ)
    if local < cutoff:
        cutoff -= dt.timedelta(days=7)
    return cutoff if cutoff >= FIRST_CUTOFF else None


def inventory(token, start, end):
    """Bounded cursor pagination; incomplete data is never counted as zero."""
    fields, errors, seen, posts, after = FIELDS, [], set(), {}, None
    for _ in range(5):
        params = {'fields': fields, 'since': int(start.timestamp()),
                  'until': int(end.timestamp()), 'limit': 100}
        if after:
            params['after'] = after
        try:
            data = native.api(base.PAGE_ID + '/posts', token, params)
        except native.Rejected as exc:
            if fields == BASIC_FIELDS:
                raise
            errors.append(str(exc))
            fields = params['fields'] = BASIC_FIELDS
            data = native.api(base.PAGE_ID + '/posts', token, params)
        if not isinstance(data.get('data'), list):
            raise ValueError('Weekly inventory missing data; no zero substitution')
        for post in data['data']:
            if post.get('is_published') is True and start <= native.stamp(post['created_time']) < end:
                posts[post['id']] = post
        paging = data.get('paging', {})
        if not paging.get('next'):
            return list(posts.values()), errors
        after = paging.get('cursors', {}).get('after')
        if not after or after in seen:
            raise ValueError('Weekly inventory incomplete or repeated cursor')
        seen.add(after)
    raise ValueError('Weekly inventory exceeds bounded pagination; no partial report')


def measured_window(token, start, end, now):
    posts, errors = inventory(token, start, end)
    rows = [three_day.row(p, now) for p in posts]
    known = {}
    for folder in ('state/meta_native', 'state/posts'):
        for path in (ROOT / folder).glob('*.json'):
            record = base.read(path)
            identity = record.get('meta_post_id') or record.get('post_id')
            if identity:
                known[identity] = record
    for row in rows:
        record = known.get(row['post_id'], {})
        slot = record.get('slot', '')
        queue = ROOT / 'queue/meta' / slot[:10] / (slot[11:].replace(':', '') + '.json')
        content = base.read(queue) if slot and queue.exists() else {}
        row.update(language=content.get('language'), topic=content.get('topic'),
                   image_sha256=record.get('image_sha256'), video_sha256=record.get('video_sha256'),
                   content_type=record.get('content_type'), style=content.get('style'))
    return {'start_inclusive': start.isoformat(), 'end_exclusive': end.isoformat(),
            'complete_inventory': True, 'published_samples': len(rows), 'posts': rows,
            'samples_at_least_48h': sum(r['age_hours'] >= 48 for r in rows),
            'samples_at_least_168h': sum(r['age_hours'] >= 168 for r in rows),
            'verified_external_interactions': None, 'non_follower_reach': None,
            'overseas_reach': None, 'errors': errors}


def run(now=None):
    now = now or dt.datetime.now(base.TZ)
    cutoff = due_cutoff(now)
    if cutoff is None:
        return
    path = ROOT / 'records/reviews' / ('weekly-' + cutoff.date().isoformat() + '.json')
    if path.exists():
        print('WEEKLY_REVIEW_ALREADY_SAVED ' + path.name)
        return
    token = os.environ.get('META_PAGE_ACCESS_TOKEN')
    if not token:
        raise ValueError('Weekly review requires existing Secret; no Facebook writes')
    identity = native.api('me', token, {'fields': 'id,name'})
    if identity.get('id') != base.PAGE_ID:
        raise ValueError('Weekly review wrong Page')
    current = measured_window(token, cutoff - dt.timedelta(days=7), cutoff, now)
    previous = measured_window(token, cutoff - dt.timedelta(days=14), cutoff - dt.timedelta(days=7), now)
    followers, errors = None, []
    try:
        followers = three_day.count(native.api('me', token, {'fields': 'id,followers_count'}).get('followers_count'))
    except native.Rejected as exc:
        errors.append(str(exc))
    result = {'page_id': base.PAGE_ID, 'review_cutoff': cutoff.isoformat(),
              'checked_at': now.isoformat(), 'executor': 'existing GitHub replenishment workflow',
              'current_window': current, 'previous_window': previous,
              'followers_observed_now': followers, 'followers_as_of_cutoff': None,
              'new_followers_attributed_to_language': None, 'errors': errors,
              'missing_data_is_zero': False, 'facebook_write_calls': 0, 'ai_calls': 0,
              'same_age_comparison_available': False,
              'decision': 'No topic/style/language winner: no matched-age reach and external-attribution evidence. Preserve controlled quality trial; investigate distribution and preparation holds first.',
              'confounding': 'Publication ages, brand, language, frequency, Reels and owner activity overlap; window totals are not causal or equal-age comparisons.',
              'owner_exclusion_policy': 'Known owner reactions excluded per post; positive residual without complete reactor identity stays unverified.',
              'legacy_weekly_report_preserved': (ROOT / 'records/reviews' / (cutoff.date().isoformat() + '-week1.json')).exists(),
              'next_cutoff': (cutoff + dt.timedelta(days=7)).isoformat()}
    base.write(path, result)
    base.persist(path, 'Save due read-only weekly Page review ' + str(cutoff.date()))
    print(json.dumps({'weekly_review': path.name, 'current_samples': current['published_samples'],
                      'previous_samples': previous['published_samples'], 'facebook_write_calls': 0, 'ai_calls': 0}))


if __name__ == '__main__':
    run()
