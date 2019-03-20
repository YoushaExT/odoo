odoo.define('web.ListModel', function (require) {
    "use strict";

    var BasicModel = require('web.BasicModel');

    var ListModel = BasicModel.extend({

        /**
         * @override
         * @param {Object} params.groupbys
         */
        init: function (parent, params) {
            this._super.apply(this, arguments);

            this.groupbys = params.groupbys;
        },

        //--------------------------------------------------------------------------
        // Public
        //--------------------------------------------------------------------------

        /**
         * Overriden to add `groupData` when performing get on list datapoints.
         *
         * @override
         * @see _readGroupExtraFields
         */
        get: function () {
            var result = this._super.apply(this, arguments);
            var dp = result && this.localData[result.id];
            if (dp && dp.groupData) {
                result.groupData = this.get(dp.groupData);
            }
            return result;
        },
        /**
         * For a list of records, performs a write with all changes and fetches
         * all data.
         *
         * @param {string} referenceRecordId the record datapoint used to
         *  generate the changes to apply to recordIds
         * @param {string[]} recordIds a list of record datapoint ids
         */
        saveRecords: function (referenceRecordId, recordIds) {
            var self = this;
            var referenceRecord = this.localData[referenceRecordId];
            var list = this.localData[referenceRecord.parentID];
            var changes = this._generateChanges(referenceRecord, {});
            var records = recordIds.map(function (recordId) {
                return self.localData[recordId];
            });
            var model = records[0].model;
            var recordResIds = _.pluck(records, 'res_id');
            var fieldNames = records[0].getFieldNames();

            return this._rpc({
                model: model,
                method: 'write',
                args: [recordResIds, changes],
                context: records[0].getContext(),
            }).then(function () {
                return self._rpc({
                    model: model,
                    method: 'read',
                    args: [recordResIds, fieldNames],
                });
            }).then(function (results) {
                results.forEach(function (data) {
                    var record = _.findWhere(records, {res_id: data.id});
                    record.data = _.extend({}, record.data, data);
                    record._changes = {};
                    record._isDirty = false;
                    self._parseServerData(fieldNames, record, record.data);
                });
            }).then(function () {
                return Promise.all([
                    self._fetchX2ManysBatched(list),
                    self._fetchReferencesBatched(list)
                ]);
            });
        },

        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         *
         * @override
         * @private
         */
        _readGroup: function (list) {
            var self = this;
            return this._super.apply(this, arguments).then(function (result) {
                var prom;
                if (!list.parentID) {
                    // groupbys buttons are only displayed on the first level of
                    // groupby so no need to fetch the extra fields for inner
                    // groups
                    prom = self._readGroupExtraFields(list);
                }
                return Promise.resolve(prom).then(_.constant(result));
            });
        },
        /**
         * Fetches group specific fields on the group by relation and stores it
         * in the column datapoint in a special key `groupData`.
         * Data for the groups are fetched in batch for all groups, to avoid
         * doing multiple calls.
         * Note that the option is only for m2o fields.
         *
         * @private
         * @param {Object} list
         * @returns {Promise}
         */
        _readGroupExtraFields: function (list) {
            var self = this;
            var groupByFieldName = list.groupedBy[0].split(':')[0];
            var groupedByField = list.fields[groupByFieldName];
            if (groupedByField.type !== 'many2one' || !this.groupbys[groupByFieldName]) {
                return Promise.resolve();
            }
            var groupIds = _.reduce(list.data, function (groupIds, id) {
                var resId = self.get(id, { raw: true }).res_id;
                if (resId) { // the field might be undefined when grouping
                    groupIds.push(resId);
                }
                return groupIds;
            }, []);
            var groupFields = Object.keys(this.groupbys[groupByFieldName].viewFields);
            var prom;
            if (groupIds.length && groupFields.length) {
                prom = this._rpc({
                    model: groupedByField.relation,
                    method: 'read',
                    args: [groupIds, groupFields],
                    context: list.context,
                });
            }
            return Promise.resolve(prom).then(function (result) {
                var fvg = self.groupbys[groupByFieldName];
                _.each(list.data, function (id) {
                    var dp = self.localData[id];
                    var groupData = result && _.findWhere(result, {
                        id: dp.res_id,
                    });
                    var groupDp = self._makeDataPoint({
                        context: dp.context,
                        data: groupData,
                        fields: fvg.fields,
                        fieldsInfo: fvg.fieldsInfo,
                        modelName: groupedByField.relation,
                        parentID: dp.id,
                        res_id: dp.res_id,
                        viewType: 'groupby',
                    });
                    dp.groupData = groupDp.id;
                });
            });
        },
    });
    return ListModel;
});
