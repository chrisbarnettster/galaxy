var RightPanel = require( 'layout/panel' ).RightPanel,
    Ui = require( 'mvc/ui/ui-misc' ),
    historyOptionsMenu = require( 'mvc/history/options-menu' );
    CurrentHistoryView = require( 'mvc/history/history-view-edit-current' ).CurrentHistoryView,
    _l = require( 'utils/localization' );

/** the right hand panel in the analysis page that shows the current history */
var HistoryPanel = RightPanel.extend({

    title : _l( 'History' ),

    initialize : function( options ){
        RightPanel.prototype.initialize.call( this, options );
        var self = this;

        // this button re-fetches the history and contents and re-renders the history panel
        this.refreshButton = new Ui.ButtonLink({
            id      : 'history-refresh-button',
            title   : _l( 'Refresh history' ),
            cls     : 'panel-header-button',
            icon    : 'fa fa-refresh',
            onclick : function() {
                self.historyView.loadCurrentHistory();
            }
        });
        // opens a drop down menu with history related functions (like view all, delete, share, etc.)
        this.optionsButton = new Ui.ButtonLink({
            id      : 'history-options-button',
            title   : _l( 'History options' ),
            cls     : 'panel-header-button',
            icon    : 'fa fa-cog',
        });
        // goes to a page showing all the users histories in panel form (for logged in users)
        this.viewMultiButton = null;
        if( !options.userIsAnonymous ){
            this.viewMultiButton = new Ui.ButtonLink({
                id      : 'history-view-multi-button',
                title   : _l( 'View all histories' ),
                cls     : 'panel-header-button',
                icon    : 'fa fa-columns',
                href    : options.galaxyRoot + 'history/view_multiple'
            });
        }

        // build history options menu
        this.optionsMenu = historyOptionsMenu( this.optionsButton.$el, {
            anonymous    : options.userIsAnonymous,
            purgeAllowed : options.allow_user_dataset_purge,
            root         : options.galaxyRoot
        });

        // view of the current history
        this.historyView = new CurrentHistoryView({
            purgeAllowed    : options.allow_user_dataset_purge,
            linkTarget      : 'galaxy_main',
            $scrollContainer: function(){ return this.$el.parent(); }
        });
    },

    render : function(){
        RightPanel.prototype.render.call( this );
        this.$( '> .header .buttons' ).append([
            this.refreshButton.$el,
            this.optionsButton.$el,
            this.viewMultiButton? this.viewMultiButton.$el : null,
        ]);
        this.historyView.setElement( this.$( '.history-panel' ) );
        this.$el.attr( 'class', 'history-right-panel' );

    },

    /** panel dom template. id is 'right' or 'left' */
    template: function(){
        return [
            this._templateHeader(),
            this._templateBody(),
            this._templateFooter(),
        ].join('');
    },

    /** panel dom template. id is 'right' or 'left' */
    _templateHeader: function( data ){
        return [
            '<div class="header">',
                '<div class="buttons" style="float: right"/>',
                '<div class="title">', _.escape( this.title ), '</div>',
            '</div>',
        ].join('');
    },

    _templateBody : function( data ){
        return [
            '<div class="middle">',
                '<div id="current-history-panel" class="history-panel"/>',
            '</div>'
        ].join('');
    },

    /** panel dom template. id is 'right' or 'left' */
    _templateFooter: function( data ){
        return [
            '<div class="footer">',
                '<div class="panel-collapse ', _.escape( this.id ), '"/>',
                '<div class="drag"/>',
            '</div>',
        ].join('');
    },

    toString : function(){ return 'HistoryPanel'; }

});

module.exports = HistoryPanel;