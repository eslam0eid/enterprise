odoo.define('helpdesk.tour', function(require) {
"use strict";

var core = require('web.core');
const {Markup} = require('web.utils');
var tour = require('web_tour.tour');

var _t = core._t;

tour.register('helpdesk_tour', {
    url: "/web",
    rainbowManMessage: Markup(_t('<center><strong><b>Good job!</b> You walked through all steps of this tour.</strong></center>')),
    sequence: 220,
}, [{
    trigger: '.o_app[data-menu-xmlid="helpdesk.menu_helpdesk_root"]',
    content: Markup(_t('Want to <b>boost your customer satisfaction</b>?<br/><i>Click Helpdesk to start.</i>')),
    position: 'bottom',
}, {
    trigger: '.oe_kanban_action_button',
    extra_trigger: '.o_kanban_primary_left',
    content: Markup(_t('Let\'s view your <b>team\'s tickets</b>.')),
    position: 'bottom',
    width: 200,
}, {
    trigger: '.o-kanban-button-new',
    extra_trigger: '.o_kanban_helpdesk_ticket',
    content: Markup(_t('Let\'s create your first <b>ticket</b>.')),
    position: 'bottom',
    width: 200,
}, {
    trigger: 'input.o_input',
    extra_trigger: '[id=name]',
    content: Markup(_t('Enter the <b>subject</b> of your ticket <br/><i>(e.g. Problem with my installation, Wrong order, etc.).</i>')),
    run: 'text SAP is bad, paid by Odoo',
    position: 'right',
}, {
    trigger: 'div[name=partner_id] input',
    content: _t('Select the <b>customer</b> of your ticket.'),
    run: 'text Deco',
    position: 'top',
}, {
    trigger: 'a.dropdown-item:contains(Deco)',
    run: 'click'
}, {
    trigger: 'button:contains(Add)',
    content: _t('Save this ticket and the modifications you\'ve made to it.'),
    position: 'bottom',
}, {
    trigger: 'span:contains(SAP is bad, paid by Odoo)',
    content: _t('Open the ticket.'),
    run: 'click',
    position: 'bottom',
}, {
    trigger: ".o_ChatterTopbar_buttonSendMessage",
    extra_trigger: '.o_form_view',
    content: Markup(_t("Use the chatter to <b>send emails</b> and communicate efficiently with your customers. \
    Add new people to the followers' list to make them aware of the progress of this ticket.")),
    width: 350,
    position: "bottom",
}, {
    trigger: ".o_ChatterTopbar_buttonLogNote",
    extra_trigger: '.o_form_view',
    content: Markup(_t("<b>Log notes</b> for internal communications (you will only notify the persons you specifically tag). \
    Use <b>@ mentions</b> to ping a colleague \
    or <b># mentions</b> to contact a group of people.")),
    width: 350,
    position: "bottom"
}, {
    trigger: ".o_ChatterTopbar_buttonScheduleActivity",
    extra_trigger: '.o_form_view',
    content: Markup(_t("Use <b>activities</b> to organize your daily work.")),
}, {
    trigger: ".modal-dialog .btn-primary",
    content: _t("Schedule your <b>activity</b>."),
    position: "right",
    run: "click",
}, {
    trigger: '.o_back_button',
    extra_trigger: '.o_form_view',
    content: _t("Let's go back to the <b>kanban view</b> to get an overview of your next tickets."),
    position: 'bottom',
}, {
    trigger: 'body:not(:has(div.o_view_sample_data)) .o_kanban_helpdesk_ticket .o_kanban_record',
    content: Markup(_t('<b>Drag &amp; drop</b> the card to change the stage of your ticket.')),
    position: 'right',
    run: "drag_and_drop .o_kanban_group:eq(2) ",
}, {
    trigger: ".o_column_quick_create .o_quick_create_folded",
    content: Markup(_t('Adapt your <b>pipeline</b> to your workflow by adding <b>stages</b> <i>(e.g. Awaiting Customer Feedback, etc.).</i>')),
    position: 'right',
}, {
    trigger: ".o_column_quick_create .o_kanban_add",
    content: Markup(_t("Add your stage and place it at the right step of your workflow by dragging & dropping it.")),
    position: 'right',
}
]);

});
