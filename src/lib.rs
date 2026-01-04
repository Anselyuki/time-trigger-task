use glob::glob;
use pyo3::prelude::*;
use serde_json::Value;
use std::fs;

// 1. 扫描目录获取 .json 文件列表 (保持不变)
#[pyfunction]
fn list_configs(dir: String) -> PyResult<Vec<String>> {
    let pattern = format!("{}/*.json", dir);
    let mut files = Vec::new();
    if let Ok(paths) = glob(&pattern) {
        for entry in paths {
            if let Ok(path) = entry {
                if let Some(path_str) = path.to_str() {
                    files.push(path_str.to_string());
                }
            }
        }
    }
    files.sort();
    Ok(files)
}

// 2. 读取 JSON (保持不变)
#[pyfunction]
fn read_config(path: String, py: Python) -> PyResult<PyObject> {
    let content = fs::read_to_string(&path).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("读取失败 {}: {}", path, e))
    })?;
    let v: Value = serde_json::from_str(&content).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("JSON 格式错误 {}: {}", path, e))
    })?;
    pythonize::pythonize(py, &v)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(e.to_string()))
}

// 3. 保存 JSON (保持不变)
#[pyfunction]
fn save_config(path: String, data: PyObject, py: Python) -> PyResult<()> {
    let v: Value = pythonize::depythonize(data.as_ref(py)).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "无法转换 Python 对象为 JSON: {}",
            e
        ))
    })?;
    let content = serde_json::to_string_pretty(&v).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("JSON 序列化失败: {}", e))
    })?;
    fs::write(&path, content).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("写入失败 {}: {}", path, e))
    })?;
    Ok(())
}

// 4. 新增: 发送 HTTP 请求
// 参数: method (GET/POST), url, payload (字典), timeout (秒)
// 返回: (status_code, response_text) 的元组
#[pyfunction]
fn send_request(
    method: String,
    url: String,
    payload: PyObject,
    timeout_secs: u64,
    py: Python,
) -> PyResult<(u16, String)> {
    // 1. 将 Python Payload 转为 Rust JSON Value
    let json_payload: Value = pythonize::depythonize(payload.as_ref(py)).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("Payload 转换失败: {}", e))
    })?;

    // 2. 构建 Client
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(timeout_secs))
        .build()
        .map_err(|e| {
            PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("构建 Client 失败: {}", e))
        })?;

    // 3. 构建请求
    let method_upper = method.to_uppercase();
    let request_builder = match method_upper.as_str() {
        "GET" => {
            // 对于 GET 请求，通常将 payload 作为 Query Params
            // 这里我们需要将 json_payload (Value) 转换成 Map 才能传给 .query()
            // 如果结构太复杂，简单处理可以直接传 json，视 API 要求而定
            // 这里为了通用性，如果方法是 GET，且 payload 是对象，则尝试转为 query
            client.get(&url).query(&json_payload)
        }
        "POST" => client.post(&url).json(&json_payload),
        "PUT" => client.put(&url).json(&json_payload),
        "DELETE" => client.delete(&url).json(&json_payload),
        _ => {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "不支持的方法: {}",
                method
            )))
        }
    };

    // 4. 发送请求
    let response = request_builder.send().map_err(|e| {
        // 将 reqwest 错误转换为 Python 异常
        PyErr::new::<pyo3::exceptions::PyConnectionError, _>(format!("网络请求失败: {}", e))
    })?;

    // 5. 获取结果
    let status = response.status().as_u16();
    let text = response.text().unwrap_or_default();

    Ok((status, text))
}

#[pymodule]
fn task_io(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(list_configs, m)?)?;
    m.add_function(wrap_pyfunction!(read_config, m)?)?;
    m.add_function(wrap_pyfunction!(save_config, m)?)?;
    // 注册新函数
    m.add_function(wrap_pyfunction!(send_request, m)?)?;
    Ok(())
}
