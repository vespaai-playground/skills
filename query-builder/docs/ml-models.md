# ML Model Integration in Rank Profiles

Load this reference when embedding ONNX, XGBoost, or LightGBM models inside a rank profile for inference at ranking time.

## ONNX Models

```sd
rank-profile onnx-ranker {
    onnx-model my_model {
        file: models/ranker.onnx
        input input_ids: my_input_tensor
        output logits: my_output
    }
    function my_input_tensor() {
        expression: tensor<float>(d0[1], d1[10])(...)
    }
    second-phase {
        expression: onnx(my_model).my_output
        rerank-count: 100
    }
}
```

## XGBoost

```sd
rank-profile xgb-ranker {
    second-phase {
        expression: xgboost("models/xgb_model.json")
        rerank-count: 200
    }
}
```

## LightGBM

```sd
rank-profile lgbm-ranker {
    second-phase {
        expression: lightgbm("models/lgbm_model.json")
        rerank-count: 200
    }
}
```

Export models as JSON under `models/`. Feature names in the exported model must match Vespa rank feature names.
