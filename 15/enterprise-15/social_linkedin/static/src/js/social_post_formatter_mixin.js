odoo.define('social_linkedin.post_formatter_mixin', function (require) {
"use strict";

var SocialPostFormatterMixin = require('social.post_formatter_mixin');
var _superFormatPost = SocialPostFormatterMixin._formatPost;

/*
 * Add LinkedIn #hashtag support.
 * Replace all occurrences of `#hashtag` by a HTML link to a search of the hashtag
 * on the media website
 */
SocialPostFormatterMixin._formatPost = function (formattedValue) {
    formattedValue = _superFormatPost.apply(this, arguments);
    var mediaType = SocialPostFormatterMixin._getMediaType.apply(this, arguments);
    if (mediaType === 'linkedin') {
        const LINKEDIN_HASHTAG_REGEX = /{hashtag\|#\|([a-zA-Z\d\-_]+)}/g;
        const hashtagReplacement = `<a href='https://www.linkedin.com/feed/hashtag/$1' target='_blank'>#$1</a>`;
        formattedValue = formattedValue.replace(SocialPostFormatterMixin.REGEX_HASHTAG, hashtagReplacement);
        formattedValue = formattedValue.replace(LINKEDIN_HASHTAG_REGEX, hashtagReplacement);
    }
    return formattedValue;
};

});
